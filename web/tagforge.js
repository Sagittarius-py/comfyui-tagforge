import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// ---------- settings ----------
const S = (id, fallback) => app.extensionManager?.setting?.get(id) ?? app.ui?.settings?.getSettingValue(id) ?? fallback;
const enabled = () => S("TagForge.Autocomplete", true);
const model = () => S("TagForge.Model", "anima");
const source = () => S("TagForge.Source", "danbooru");

const CAT_COLORS = { general: "#7aa2f7", artist: "#f7768e", copyright: "#bb9af7", character: "#9ece6a",
  meta: "#e0af68", species: "#ff9e64", lore: "#73daca", invalid: "#888" };

const css = `
.tf-drop{position:fixed;z-index:10000;background:#1e1e2a;border:1px solid #444;border-radius:6px;
  font:12px sans-serif;color:#ddd;min-width:260px;max-height:320px;overflow:auto;box-shadow:0 6px 20px #0008}
.tf-item{display:flex;gap:8px;padding:4px 8px;cursor:pointer;align-items:baseline}
.tf-item.sel,.tf-item:hover{background:#333a55}
.tf-item .n{flex:1}.tf-item .a{color:#888;font-size:11px}.tf-item .c{color:#999;font-size:11px}
.tf-bad{outline:2px solid #e0af68 !important}.tf-blocked{outline:2px solid #f7768e !important}
.tf-modal{position:fixed;inset:5%;z-index:10001;background:#181820;border:1px solid #444;border-radius:10px;
  display:flex;flex-direction:column;color:#ddd;font:13px sans-serif}
.tf-modal header{display:flex;gap:8px;padding:10px;border-bottom:1px solid #333;align-items:center;flex-wrap:wrap}
.tf-modal .tabs{display:flex;gap:4px}
.tf-modal input[type=text]{flex:1;padding:6px;background:#222;color:#ddd;border:1px solid #444;border-radius:4px}
.tf-modal select,.tf-modal button{padding:6px;background:#2a2a38;color:#ddd;border:1px solid #444;border-radius:4px}
.tf-list{flex:1;overflow:auto;padding:6px 10px}
.tf-row{display:flex;gap:12px;align-items:center;padding:6px 8px;border-bottom:1px solid #2a2a35;cursor:pointer}
.tf-row:hover{background:#262636}.tf-row.added .t{color:#9ece6a}
.tf-row .t{flex:1;word-break:break-word}.tf-row .c{color:#999;font-variant-numeric:tabular-nums}
.tf-row a{color:#7aa2f7;text-decoration:none}.tf-row a:hover{text-decoration:underline}
.tf-rt{display:flex;flex-direction:column;gap:6px;height:100%;font:12px sans-serif}
.tf-rt-bar{display:flex;flex-wrap:wrap;gap:4px}
.tf-rt-bar button{background:#333;color:#ccc;border:1px solid #555;border-radius:6px 6px 0 0;padding:3px 9px;cursor:pointer}
.tf-rt-bar button.on{background:#4a6fa5;color:#fff;border-color:#6d8fc4}
.tf-rt textarea{flex:1;min-height:120px;resize:none;background:#1e1e1e;color:#ddd;border:1px solid #555;border-radius:4px;padding:6px;font:12px monospace}
.tf-rt-info{color:#999;padding:6px}`;

// window.prompt/confirm do nothing in ComfyUI Desktop, so use ComfyUI's own dialogs
const ask = (title, defaultValue = "") => app.extensionManager.dialog.prompt({ title, message: title, defaultValue });
const sure = (message) => app.extensionManager.dialog.confirm({ title: "TagForge", message });

// ---------- autocomplete ----------
let drop = null, items = [], sel = 0, target = null, reqId = 0;

function closeDrop() { drop?.remove(); drop = null; items = []; }

function currentToken(ta) {
  const pos = ta.selectionStart, text = ta.value.slice(0, pos);
  const start = Math.max(text.lastIndexOf(","), text.lastIndexOf("\n")) + 1;
  const raw = text.slice(start);
  const lead = raw.match(/^[\s(@]*/)[0];
  return { start: start + lead.length, end: pos, word: raw.slice(lead.length) };
}

function display(name) {
  const t = /^score_\d+/.test(name) ? name : name.replace(/_/g, " ");
  return t.replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}

function insert(ta, item) {
  const tok = currentToken(ta);
  let text = display(item.name);
  const before = ta.value.slice(0, tok.start);
  if (item.category_name === "artist" && model() === "anima" && !before.endsWith("@")) text = "@" + text;
  if (item.category_name === "artist" && model() !== "anima" && before.endsWith("@"))
    ta.value = before.slice(0, -1) + ta.value.slice(tok.start), tok.start--, tok.end--;
  const after = ta.value.slice(tok.end).replace(/^[^,\n]*/, "");
  const sep = after.startsWith(",") ? "" : ", ";
  ta.value = ta.value.slice(0, tok.start) + text + sep + after;
  const caret = tok.start + text.length + sep.length + (sep ? 0 : 1);
  ta.setSelectionRange(caret, caret);
  ta.dispatchEvent(new Event("input", { bubbles: true }));
  closeDrop();
}

function render(ta) {
  if (!items.length) return closeDrop();
  if (!drop) { drop = document.createElement("div"); drop.className = "tf-drop"; document.body.appendChild(drop); }
  const r = ta.getBoundingClientRect();
  drop.style.left = `${r.left}px`;
  drop.style.top = `${Math.min(r.bottom + 2, innerHeight - 330)}px`;
  drop.innerHTML = "";
  items.forEach((it, i) => {
    const row = document.createElement("div");
    row.className = "tf-item" + (i === sel ? " sel" : "");
    row.innerHTML = `<span class="n" style="color:${CAT_COLORS[it.category_name] || "#ddd"}"></span>
      <span class="a"></span><span class="c"></span>`;
    row.querySelector(".n").textContent = display(it.name);
    row.querySelector(".a").textContent = it.alias ? `← ${it.alias}` : (it.source === "e621" ? "e621" : "");
    row.querySelector(".c").textContent = it.count >= 1000 ? `${(it.count / 1000).toFixed(1)}k` : it.count;
    row.addEventListener("mousedown", (e) => { e.preventDefault(); insert(ta, it); });
    drop.appendChild(row);
  });
  drop.children[sel]?.scrollIntoView({ block: "nearest" });
}

async function suggest(ta) {
  const { word } = currentToken(ta);
  if (word.trim().length < 2 || word.split(/\s+/).length > 5) return closeDrop();
  const id = ++reqId;
  const res = await api.fetchApi(`/tagforge/search?q=${encodeURIComponent(word)}&source=${source()}`);
  if (id !== reqId || document.activeElement !== ta) return;
  items = res.ok ? await res.json() : [];
  sel = 0; target = ta; render(ta);
}

let timer = null;
document.addEventListener("input", (e) => {
  const ta = e.target;
  if (!enabled() || ta.tagName !== "TEXTAREA" || ta.closest(".tf-modal") || e.isTrusted === false) return;
  clearTimeout(timer);
  timer = setTimeout(() => suggest(ta), 120);
}, true);

document.addEventListener("keydown", (e) => {
  if (!drop || e.target !== target) return;
  const keys = { ArrowDown: 1, ArrowUp: -1 };
  if (e.key in keys) sel = (sel + keys[e.key] + items.length) % items.length, render(target);
  else if (e.key === "Enter" || e.key === "Tab") insert(target, items[sel]);
  else if (e.key === "Escape") closeDrop();
  else return;
  e.preventDefault(); e.stopPropagation();
}, true);

// ---------- unknown / blocked tag check on blur ----------
document.addEventListener("focusout", async (e) => {
  const ta = e.target;
  if (ta.tagName !== "TEXTAREA" || ta.closest(".tf-modal")) return;
  closeDrop();
  if (!enabled() || !ta.value.trim()) return ta.classList.remove("tf-bad", "tf-blocked");
  const res = await api.fetchApi("/tagforge/check", { method: "POST",
    body: JSON.stringify({ text: ta.value, model: model(), source: source() }) });
  if (!res.ok) return;
  const { unknown, blocked } = await res.json();
  ta.classList.toggle("tf-blocked", blocked.length > 0);
  ta.classList.toggle("tf-bad", !blocked.length && unknown.length > 0);
  ta.title = [blocked.length ? `BLOCKED: ${blocked.join(", ")}` : "",
    unknown.length ? `Unknown tags: ${unknown.join(", ")}` : ""].filter(Boolean).join("\n");
}, true);

// ---------- artist browser ----------
const canon = (s) => s.trim().replace(/^\(/, "").replace(/:[0-9.]+\)$/, "").replace(/^@/, "").replace(/\\/g, "")
  .replace(/\s+/g, "_").toLowerCase();
const profileUrl = (name) => "https://danbooru.donmai.us/artists/show_or_new?name=" + encodeURIComponent(name);

async function saveLists(update) {
  const res = await api.fetchApi("/tagforge/lists", { method: "POST", body: JSON.stringify(update) });
  if (!res.ok) throw new Error((await res.json()).error || res.statusText);
}

function openArtists(node) {
  const widget = node.widgets.find((w) => w.name === "artists");
  const modelW = node.widgets.find((w) => w.name === "model");
  const m = document.createElement("div");
  m.className = "tf-modal";
  m.innerHTML = `<header><div class="tabs"><button data-tab="all">All</button><button data-tab="fav">★ Favorites</button>
    <button data-tab="ban">⛔ Blacklist</button><button data-tab="presets">Presets</button></div>
    <input type="text" placeholder="Search artists…">
    <select class="mdl"><option value="anima">Anima</option><option value="illustrious">Illustrious</option></select>
    <button class="save">Save current as preset</button><button class="close">Close</button></header>
    <div class="tf-list"></div><footer style="padding:8px;text-align:center"><button class="more">More</button></footer>`;
  document.body.appendChild(m);
  const [q, mdl, grid, more] = ["input[type=text]", ".mdl", ".tf-list", ".more"].map((s) => m.querySelector(s));
  mdl.value = modelW?.value || "anima";
  let offset = 0, tab = "all", lists = { favorites: [], blacklist: [], presets: [], builtin: [] };
  const fmt = (name) => (mdl.value === "anima" ? "@" : "") + display(name);
  const chosen = () => new Set(widget.value.split(/[,\n]/).map(canon).filter(Boolean));

  function append(text) {
    const v = widget.value.trim();
    widget.value = (v ? v.replace(/,?$/, ",\n") : "") + text;
    widget.callback?.(widget.value);
    app.graph.setDirtyCanvas(true, true);
  }

  async function toggle(key, name) {
    const set = new Set(lists[key]);
    set.has(name) ? set.delete(name) : set.add(name);
    lists[key] = [...set];
    await saveLists({ [key]: lists[key] });
  }

  function artistRow(name, extra) {
    const c = document.createElement("div");
    c.className = "tf-row" + (chosen().has(name) ? " added" : "");
    c.innerHTML = `<span class="t"></span><span class="c"></span><button class="fav" title="Favorite"></button>
      <button class="ban" title="Blacklist: never picked at random, hidden from All"></button><a target="_blank" rel="noopener">profile ↗</a>`;
    c.querySelector(".t").textContent = fmt(name);
    c.querySelector(".c").textContent = extra || "";
    const fav = c.querySelector(".fav"), ban = c.querySelector(".ban");
    const paint = () => {
      fav.textContent = lists.favorites.includes(name) ? "★" : "☆";
      ban.textContent = lists.blacklist.includes(name) ? "Unban" : "⛔";
    };
    paint();
    fav.addEventListener("click", async (e) => {
      e.stopPropagation();
      await toggle("favorites", name); paint();
      if (tab === "fav") c.remove();
    });
    ban.addEventListener("click", async (e) => {
      e.stopPropagation();
      await toggle("blacklist", name); paint();
      if (tab !== "fav") c.remove();
    });
    const link = c.querySelector("a");
    link.href = profileUrl(name);
    link.addEventListener("click", (e) => e.stopPropagation());
    c.addEventListener("click", () => { append(fmt(name)); c.classList.add("added"); });
    return c;
  }

  function presetRow(p, own) {
    const c = document.createElement("div");
    c.className = "tf-row";
    c.innerHTML = `<span class="t"><b></b><br><small class="a"></small><br><small class="d" style="color:#999"></small></span>`;
    c.querySelector("b").textContent = p.name;
    c.querySelector(".a").textContent = p.artists;
    c.querySelector(".d").textContent = p.look || "";
    if (own) {
      const del = document.createElement("button");
      del.textContent = "Delete";
      del.addEventListener("click", async (e) => {
        e.stopPropagation();
        lists.presets = lists.presets.filter((x) => x !== p);
        await saveLists({ presets: lists.presets });
        c.remove();
      });
      c.appendChild(del);
    } else if (p.source) {
      const a = document.createElement("a");
      Object.assign(a, { href: p.source, target: "_blank", rel: "noopener", textContent: "source ↗" });
      a.addEventListener("click", (e) => e.stopPropagation());
      c.appendChild(a);
    }
    c.addEventListener("click", () => { append(p.artists); c.classList.add("added"); });
    return c;
  }

  function heading(text) {
    const h = document.createElement("div");
    h.style.cssText = "padding:10px 8px 4px;color:#e0af68;font-weight:bold";
    h.textContent = text;
    grid.appendChild(h);
  }

  async function load(reset) {
    if (reset) { offset = 0; grid.innerHTML = ""; }
    m.querySelectorAll(".tabs button").forEach((b) => b.style.outline = b.dataset.tab === tab ? "1px solid #7aa2f7" : "");
    more.style.display = tab === "all" ? "" : "none";
    const needle = canon(q.value);
    if (tab === "fav" || tab === "ban") {
      const names = (tab === "fav" ? lists.favorites : lists.blacklist).filter((n) => n.includes(needle));
      if (!names.length) grid.textContent = tab === "fav" ? "No favorites yet - click ☆ next to an artist." : "Blacklist is empty.";
      for (const n of names) grid.appendChild(artistRow(n, ""));
      return;
    }
    if (tab === "presets") {
      const match = (p) => (p.name + " " + p.artists).toLowerCase().includes(q.value.trim().toLowerCase());
      heading("Your presets");
      const own = lists.presets.filter(match);
      if (!own.length) grid.insertAdjacentHTML("beforeend", `<div style="padding:6px 8px;color:#888">None yet - build a mix in the node and click “Save current as preset”.</div>`);
      own.forEach((p) => grid.appendChild(presetRow(p, true)));
      heading("Built-in presets (Illustrious / NoobAI)");
      lists.builtin.filter(match).forEach((p) => grid.appendChild(presetRow(p, false)));
      return;
    }
    const p = new URLSearchParams({ q: q.value, model: mdl.value, offset });
    const data = await (await api.fetchApi(`/tagforge/artists?${p}`)).json();
    if (!data.db) { grid.textContent = "No tag database - run scripts/build_db.py and restart ComfyUI."; return; }
    offset = data.next;
    for (const it of data.items)
      if (!lists.blacklist.includes(it.name)) grid.appendChild(artistRow(it.name, `${it.count.toLocaleString()} posts`));
  }

  let t = null;
  q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => load(true), 250); });
  mdl.addEventListener("change", () => load(true));
  more.addEventListener("click", () => load(false));
  m.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => { tab = b.dataset.tab; load(true); }));
  m.querySelector(".save").addEventListener("click", async () => {
    const artists = widget.value.trim().replace(/,\s*$/, "");
    if (!artists) return alert("The artists field is empty.");
    const name = await ask("Preset name:");
    if (!name?.trim()) return;
    lists.presets = [...lists.presets, { name: name.trim(), artists }];
    await saveLists({ presets: lists.presets });
    if (tab === "presets") load(true);
  });
  m.querySelector(".close").addEventListener("click", () => m.remove());
  m.addEventListener("keydown", (e) => { e.stopPropagation(); if (e.key === "Escape") m.remove(); });
  api.fetchApi("/tagforge/lists").then((r) => r.json()).then((l) => { lists = l; load(true); });
  q.focus();
}

// ---------- Random Text: tabs of options, stored as JSON in the hidden "data" widget ----------
const RANDOM_TAB = "*";

function randomTextTabs(node) {
  const data = node.widgets.find((w) => w.name === "data");
  data.hidden = true;
  const root = document.createElement("div");
  root.className = "tf-rt";
  const bar = document.createElement("div");
  bar.className = "tf-rt-bar";
  const area = document.createElement("textarea");
  area.placeholder = "One option per line, # = comment";
  const info = document.createElement("div");
  info.className = "tf-rt-info";
  root.append(bar, area, info);

  const state = () => JSON.parse(data.value);
  const save = (s) => { data.value = JSON.stringify(s); render(); };
  const button = (label, title, onclick, on = false) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.title = title;
    b.className = on ? "on" : "";
    b.onclick = onclick;
    bar.append(b);
    return b;
  };
  const newName = async (title, current = "") => {
    const name = (await ask(title, current))?.trim();
    return name && !state().tabs.some((t) => t.name === name) ? name : null;
  };

  // handlers read the state when clicked, so text typed since the last render is kept
  function render() {
    const s = state();
    bar.replaceChildren();
    for (const { name } of s.tabs) {
      const b = button(name, "Click: use this tab · double-click: rename", () => save({ ...state(), active: name }), s.active === name);
      b.ondblclick = async () => {
        const renamed = await newName("Rename tab:", name);
        if (!renamed) return;
        const cur = state();
        if (cur.active === name) cur.active = renamed;
        cur.tabs.find((t) => t.name === name).name = renamed;
        save(cur);
      };
    }
    button("🎲", "Random tab", () => save({ ...state(), active: RANDOM_TAB }), s.active === RANDOM_TAB);
    button("+", "Add tab", async () => {
      const name = await newName("New tab name:");
      if (!name) return;
      const cur = state();
      cur.tabs.push({ name, text: "" });
      save({ ...cur, active: name });
    });
    const tab = s.tabs.find((t) => t.name === s.active);
    if (tab) {
      button("×", `Delete tab "${tab.name}"`, async () => {
        if (!(await sure(`Delete tab "${tab.name}" and its options?`))) return;
        const cur = state();
        cur.tabs = cur.tabs.filter((t) => t.name !== tab.name);
        save({ ...cur, active: cur.tabs[0]?.name ?? RANDOM_TAB });
      });
    }
    area.style.display = tab ? "" : "none";
    info.style.display = tab ? "none" : "";
    info.textContent = `Picks a random tab from: ${s.tabs.map((t) => t.name).join(", ") || "(no tabs)"}`;
    if (tab && area.value !== tab.text) area.value = tab.text;
  }

  area.oninput = () => {
    const s = state();
    s.tabs.find((t) => t.name === s.active).text = area.value;
    data.value = JSON.stringify(s);
  };
  node.addDOMWidget("tabs", "tagforge_tabs", root, { serialize: false, getMinHeight: () => 200 });
  render();
  const configure = node.onConfigure;
  node.onConfigure = function () {
    const r = configure?.apply(this, arguments);
    render();
    return r;
  };
}

app.registerExtension({
  name: "TagForge",
  settings: [
    { id: "TagForge.Autocomplete", name: "TagForge: tag autocomplete and checking", type: "boolean", defaultValue: true },
    { id: "TagForge.Model", name: "TagForge: artist syntax (Anima = @name)", type: "combo",
      options: ["anima", "illustrious"], defaultValue: "anima" },
    { id: "TagForge.Source", name: "TagForge: suggestion source", type: "combo",
      options: ["danbooru", "e621", "both"], defaultValue: "danbooru" },
  ],
  setup() {
    const style = document.createElement("style");
    style.textContent = css;
    document.head.appendChild(style);
  },
  nodeCreated(node) {
    if (node.comfyClass === "TagForgeArtists")
      node.addWidget("button", "Browse artists…", null, () => openArtists(node), { serialize: false });
    if (node.comfyClass === "TagForgeRandomText") randomTextTabs(node);
  },
});
