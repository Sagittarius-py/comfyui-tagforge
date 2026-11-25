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
.tf-modal header{display:flex;gap:8px;padding:10px;border-bottom:1px solid #333;align-items:center}
.tf-modal input[type=text]{flex:1;padding:6px;background:#222;color:#ddd;border:1px solid #444;border-radius:4px}
.tf-modal select,.tf-modal button{padding:6px;background:#2a2a38;color:#ddd;border:1px solid #444;border-radius:4px}
.tf-list{flex:1;overflow:auto;padding:6px 10px}
.tf-row{display:flex;gap:12px;align-items:center;padding:6px 8px;border-bottom:1px solid #2a2a35;cursor:pointer}
.tf-row:hover{background:#262636}.tf-row.added .t{color:#9ece6a}
.tf-row .t{flex:1;word-break:break-word}.tf-row .c{color:#999;font-variant-numeric:tabular-nums}
.tf-row a{color:#7aa2f7;text-decoration:none}.tf-row a:hover{text-decoration:underline}`;

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
  ta.title = [blocked.length ? `ZABLOKOWANE: ${blocked.join(", ")}` : "",
    unknown.length ? `Nieznane tagi: ${unknown.join(", ")}` : ""].filter(Boolean).join("\n");
}, true);

// ---------- artist browser ----------
function openArtists(node) {
  const widget = node.widgets.find((w) => w.name === "artists");
  const modelW = node.widgets.find((w) => w.name === "model");
  const m = document.createElement("div");
  m.className = "tf-modal";
  m.innerHTML = `<header><input type="text" placeholder="Szukaj artysty…">
    <select class="mdl"><option value="anima">Anima</option><option value="illustrious">Illustrious</option></select>
    <button class="close">Zamknij</button></header><div class="tf-list"></div>
    <footer style="padding:8px;text-align:center"><button class="more">Więcej</button></footer>`;
  document.body.appendChild(m);
  const [q, mdl, grid] = ["input[type=text]", ".mdl", ".tf-list"].map((s) => m.querySelector(s));
  mdl.value = modelW?.value || "anima";
  let offset = 0;
  const chosen = () => new Set(widget.value.split(/[,\n]/).map((s) => s.trim().replace(/^@/, "").replace(/\\/g, "")
    .replace(/ /g, "_").toLowerCase()).filter(Boolean));

  async function load(reset) {
    if (reset) { offset = 0; grid.innerHTML = ""; }
    const p = new URLSearchParams({ q: q.value, model: mdl.value, offset });
    const res = await api.fetchApi(`/tagforge/artists?${p}`);
    const data = await res.json();
    if (!data.db) { grid.textContent = "Brak bazy - uruchom scripts/build_db.py i zrestartuj ComfyUI."; return; }
    offset = data.next;
    const have = chosen();
    for (const it of data.items) {
      const c = document.createElement("div");
      c.className = "tf-row" + (have.has(it.name) ? " added" : "");
      c.innerHTML = `<span class="t"></span><span class="c"></span><a target="_blank" rel="noopener">profil ↗</a>`;
      c.querySelector(".t").textContent = it.text;
      c.querySelector(".c").textContent = `${it.count.toLocaleString("pl-PL")} postów`;
      const link = c.querySelector("a");
      link.href = it.url;
      link.addEventListener("click", (e) => e.stopPropagation());
      c.addEventListener("click", () => {
        const v = widget.value.trim();
        widget.value = (v ? v.replace(/,?$/, ",\n") : "") + it.text;
        widget.callback?.(widget.value);
        c.classList.add("added");
        app.graph.setDirtyCanvas(true, true);
      });
      grid.appendChild(c);
    }
  }
  let t = null;
  q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => load(true), 250); });
  mdl.addEventListener("change", () => load(true));
  m.querySelector(".more").addEventListener("click", () => load(false));
  m.querySelector(".close").addEventListener("click", () => m.remove());
  m.addEventListener("keydown", (e) => { e.stopPropagation(); if (e.key === "Escape") m.remove(); });
  load(true);
  q.focus();
}

app.registerExtension({
  name: "TagForge",
  settings: [
    { id: "TagForge.Autocomplete", name: "TagForge: autouzupełnianie i sprawdzanie tagów", type: "boolean", defaultValue: true },
    { id: "TagForge.Model", name: "TagForge: składnia artystów (Anima = @nazwa)", type: "combo",
      options: ["anima", "illustrious"], defaultValue: "anima" },
    { id: "TagForge.Source", name: "TagForge: źródło podpowiedzi", type: "combo",
      options: ["danbooru", "e621", "both"], defaultValue: "danbooru" },
  ],
  setup() {
    const style = document.createElement("style");
    style.textContent = css;
    document.head.appendChild(style);
  },
  nodeCreated(node) {
    if (node.comfyClass === "TagForgeArtists")
      node.addWidget("button", "Przeglądaj artystów…", null, () => openArtists(node), { serialize: false });
  },
});
