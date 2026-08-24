"use strict";

const TOKEN = document.body.dataset.token;
const $ = (selector) => document.querySelector(selector);
const A4_PIXELS = 794;                       // 210 mm at 96 dpi

let DATA = null;
let INFO = null;
let SETTINGS = null;
let previewAbort = null;
let previewTimer = null;
let saveTimer = null;
let zoom = 1;
let fitMode = true;
let docKind = "resume";        // resume | letter | both

/* Preference store: embedded WebViews in private mode have no localStorage,
   in which case everything falls back to memory. */
const store = (() => {
  const memory = new Map();
  let real = false;
  try {
    if (typeof localStorage !== "undefined" && localStorage) {
      localStorage.setItem("cvboreout.probe", "1");
      localStorage.removeItem("cvboreout.probe");
      real = true;
    }
  } catch (error) {
    real = false;
  }
  return {
    available: real,
    get(key, fallback = "") {
      try {
        const value = real ? localStorage.getItem(key) : memory.get(key);
        return value === null || value === undefined ? fallback : value;
      } catch (error) {
        return fallback;
      }
    },
    set(key, value) {
      try {
        if (real) localStorage.setItem(key, value);
        else memory.set(key, value);
      } catch (error) {
        memory.set(key, value);
      }
    },
  };
})();

/* ------------------------------------------------------------- language */

function language() {
  return (DATA && DATA.meta && DATA.meta.language) || "de";
}

function t(key) {
  const table = STRINGS[language()] || STRINGS.de;
  return table[key] || STRINGS.de[key] || key;
}

function translateStatic() {
  document.documentElement.lang = language();
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = t(node.dataset.i18n);
  }
  for (const node of document.querySelectorAll("[data-i18n-title]")) {
    node.title = t(node.dataset.i18nTitle);
  }
  for (const node of document.querySelectorAll("[data-i18n-placeholder]")) {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  }
}

/* ----------------------------------------------------------------- net */

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.body ? "POST" : "GET",
    headers: { "Content-Type": "application/json", "X-Token": TOKEN },
    body: options.body ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  });
  const result = await response.json();
  if (!response.ok || result.error) throw new Error(result.error || response.statusText);
  return result;
}

function toast(message, isError = false) {
  const box = $("#toast");
  box.textContent = message;
  box.classList.toggle("error", isError);
  box.hidden = false;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => (box.hidden = true), isError ? 6000 : 2800);
}

function setStatus(key, className = "") {
  const node = $("#status");
  node.textContent = t(key);
  node.className = "status " + className;
}

function copyText(text) {
  const done = () => toast(t("msg.copied"));
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done));
  } else {
    fallbackCopy(text, done);
  }
}

function fallbackCopy(text, done) {
  const field = document.createElement("textarea");
  field.value = text;
  field.style.position = "fixed";
  field.style.opacity = "0";
  document.body.append(field);
  field.select();
  try {
    document.execCommand("copy");
    done();
  } catch (error) {
    toast(t("msg.copyFailed"), true);
  }
  field.remove();
}

/* ----------------------------------------------------------- building */

function el(tag, properties = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(properties)) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value !== undefined && value !== null) node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) if (child) node.append(child);
  return node;
}

function field(label, ...content) {
  return el("label", { class: "field" }, [
    label ? el("span", { class: "label", text: label }) : null,
    ...content,
  ]);
}

function input(owner, key, options = {}) {
  const node = el(options.rows ? "textarea" : "input", {
    placeholder: options.placeholder || "",
    rows: options.rows || undefined,
    type: options.type || undefined,
  });
  node.value = owner[key] ?? "";
  node.addEventListener("input", () => {
    owner[key] = node.value;
    if (options.title) options.title.textContent = node.value || options.emptyTitle || "—";
    changed();
  });
  return node;
}

function select(owner, key, entries, onChange) {
  const node = el("select");
  for (const entry of entries) node.append(el("option", { value: entry.value, text: entry.name }));
  node.value = owner[key];
  node.addEventListener("change", () => {
    owner[key] = node.value;
    changed();
    if (onChange) onChange(node.value);
  });
  return node;
}

function toggle(owner, key, label) {
  const box = el("input", { type: "checkbox" });
  box.checked = !!owner[key];
  box.addEventListener("change", () => {
    owner[key] = box.checked;
    changed();
  });
  return el("label", { class: "switch" }, [box, el("span", { text: label })]);
}

function levels(owner, key = "level") {
  const holder = el("div", { class: "levels" });
  const draw = () => {
    holder.textContent = "";
    for (let i = 1; i <= 5; i++) {
      holder.append(el("i", {
        class: i <= (owner[key] || 0) ? "on" : "",
        title: String(i),
        onclick: () => {
          owner[key] = owner[key] === i ? i - 1 : i;
          draw();
          changed();
        },
      }));
    }
  };
  draw();
  holder.refresh = draw;
  return holder;
}

function card(titleText, onRemove, onMove, children) {
  const title = el("span", { class: "title", text: titleText || "—" });
  const head = el("div", { class: "card-head" }, [
    title,
    el("button", { title: t("act.up"), text: "↑", onclick: () => onMove(-1) }),
    el("button", { title: t("act.down"), text: "↓", onclick: () => onMove(1) }),
    el("button", { title: t("act.delete"), text: "×", onclick: onRemove }),
  ]);
  return { node: el("div", { class: "card" }, [head, ...children]), title };
}

function group(title, count, body, open = false) {
  const head = el("summary", {}, [
    el("span", { text: title }),
    count !== null ? el("span", { class: "count", text: String(count) }) : null,
  ]);
  return el("details", { class: "group", ...(open ? { open: "" } : {}) }, [
    head,
    el("div", { class: "group-body" }, body),
  ]);
}

/* --------------------------------------------------------- date widgets */

const THIS_YEAR = new Date().getFullYear();

function yearOptions(withPresent) {
  const options = [{ value: "", name: "—" }];
  if (withPresent) options.push({ value: "present", name: t("f.present") });
  for (let year = THIS_YEAR + 1; year >= THIS_YEAR - 55; year--) {
    options.push({ value: String(year), name: String(year) });
  }
  return options;
}

function parseDate(raw) {
  const value = String(raw || "").trim();
  if (!value) return { month: "", year: "" };
  if (value.toLowerCase() === "present") return { month: "", year: "present" };
  let match = value.match(/^(\d{1,2})[./-](\d{4})$/);
  if (match) return { month: match[1].padStart(2, "0"), year: match[2] };
  match = value.match(/^(\d{4})$/);
  if (match) return { month: "", year: match[1] };
  return { month: "", year: value, custom: true };
}

/** Month + year dropdown pair writing back a "MM/YYYY" string. */
function dateControl(owner, key, options = {}) {
  const parsed = parseDate(owner[key]);
  const monthSelect = el("select", { title: t("f.month") });
  monthSelect.append(el("option", { value: "", text: "—" }));
  (MONTHS[language()] || MONTHS.de).forEach((name, index) => {
    const value = String(index + 1).padStart(2, "0");
    monthSelect.append(el("option", { value, text: `${value} ${name}` }));
  });

  const yearSelect = el("select", { title: t("f.year") });
  const years = yearOptions(!!options.allowPresent);
  if (parsed.custom) years.splice(1, 0, { value: parsed.year, name: parsed.year });
  for (const entry of years) yearSelect.append(el("option", { value: entry.value, text: entry.name }));

  monthSelect.value = parsed.month;
  yearSelect.value = parsed.year;

  const write = () => {
    const year = yearSelect.value;
    const month = monthSelect.value;
    monthSelect.disabled = year === "present" || !year;
    if (year === "present") owner[key] = "present";
    else if (!year) owner[key] = "";
    else owner[key] = month ? `${month}/${year}` : year;
    changed();
  };
  monthSelect.disabled = parsed.year === "present" || !parsed.year;
  monthSelect.addEventListener("change", write);
  yearSelect.addEventListener("change", write);
  return el("div", { class: "row date" }, [monthSelect, yearSelect]);
}

function yearControl(owner, key) {
  const node = el("select");
  const current = String(owner[key] || "").trim();
  const options = yearOptions(false);
  if (current && !options.some((o) => o.value === current)) {
    options.splice(1, 0, { value: current, name: current });
  }
  for (const entry of options) node.append(el("option", { value: entry.value, text: entry.name }));
  node.value = current;
  node.addEventListener("change", () => {
    owner[key] = node.value;
    changed();
  });
  return node;
}

function proficiencySelect(owner, dots) {
  const node = el("select");
  const current = owner.proficiency || "";
  const options = INFO.proficiency.map((entry) => ({
    value: entry.id,
    name: entry[language()] || entry.en,
  }));
  if (current === "custom" || (current && !options.some((o) => o.value === current))) {
    options.unshift({ value: current || "custom", name: owner.proficiencyLabel || current });
  }
  options.unshift({ value: "", name: "—" });
  for (const entry of options) node.append(el("option", { value: entry.value, text: entry.name }));
  node.value = current;
  node.addEventListener("change", () => {
    owner.proficiency = node.value;
    const preset = INFO.proficiency.find((entry) => entry.id === node.value);
    if (preset) {
      owner.level = preset.level;
      if (dots && dots.refresh) dots.refresh();
    }
    changed();
  });
  return node;
}

/* ------------------------------------------------------- list widgets */

/** One row per value – used for technologies and interests. */
function tagList(owner, key, options = {}) {
  const holder = el("div", { class: "taglist" });
  const values = owner[key];
  const draw = () => {
    holder.textContent = "";
    values.forEach((value, index) => {
      const node = el("input", { placeholder: options.placeholder || "" });
      node.value = value;
      node.addEventListener("input", () => {
        values[index] = node.value;
        changed();
      });
      holder.append(el("div", { class: "row" }, [
        node,
        el("button", {
          class: "btn tiny", text: "×", title: t("act.delete"),
          onclick: () => { values.splice(index, 1); draw(); changed(); },
        }),
      ]));
    });
    holder.append(el("button", {
      class: "add", text: "+ " + (options.addLabel || ""),
      onclick: () => { values.push(""); draw(); focusLast(holder); changed(); },
    }));
  };
  draw();
  return holder;
}

function focusLast(holder) {
  const fields = holder.querySelectorAll("input, textarea");
  if (fields.length) fields[fields.length - 1].focus();
}

function autoGrow(node) {
  node.style.height = "auto";
  node.style.height = Math.max(34, node.scrollHeight) + "px";
}

/** One growing text box per bullet point, with reordering. */
function bulletList(owner, key) {
  const holder = el("div", { class: "bullets" });
  const values = owner[key];
  const draw = () => {
    holder.textContent = "";
    values.forEach((value, index) => {
      const box = el("textarea", { rows: 1 });
      box.value = value;
      box.addEventListener("input", () => {
        values[index] = box.value;
        autoGrow(box);
        changed();
      });
      const move = (direction) => {
        const target = index + direction;
        if (target < 0 || target >= values.length) return;
        [values[index], values[target]] = [values[target], values[index]];
        draw();
        changed();
      };
      holder.append(el("div", { class: "bullet" }, [
        box,
        el("div", { class: "arrows" }, [
          el("button", { text: "▲", title: t("act.up"), onclick: () => move(-1) }),
          el("button", { text: "▼", title: t("act.down"), onclick: () => move(1) }),
        ]),
        el("button", {
          class: "btn tiny", text: "×", title: t("act.delete"),
          onclick: () => { values.splice(index, 1); draw(); changed(); },
        }),
      ]));
      requestAnimationFrame(() => autoGrow(box));
    });
    holder.append(el("button", {
      class: "add", text: "+ " + t("f.addBullet"),
      onclick: () => { values.push(""); draw(); focusLast(holder); changed(); },
    }));
  };
  draw();
  return holder;
}

/* --------------------------------------------------------- list sections */

function LISTS() {
  return {
    experience: {
      create: () => ({ position: "", company: "", location: "", from: "", to: "",
                       bullets: [], tech: [] }),
      head: (entry) => entry.position || t("new.experience"),
      fields: (entry, title, index) => [
        field(t("f.position"), input(entry, "position", { title, emptyTitle: t("new.experience") })),
        el("div", { class: "grid2" }, [
          field(t("f.company"), input(entry, "company")),
          field(t("f.location"), input(entry, "location")),
        ]),
        el("div", { class: "grid2" }, [
          field(t("f.from"), dateControl(entry, "from")),
          field(t("f.to"), dateControl(entry, "to", { allowPresent: true })),
        ]),
        field(t("f.bullets"), bulletList(entry, "bullets")),
        field(t("f.tech"), tagList(entry, "tech", { placeholder: "C, FreeRTOS…", addLabel: t("f.addTech") })),
        el("button", {
          class: "ai-btn", text: "✦ " + t("ai.bullets"),
          onclick: () => openAI("bullets", index),
        }),
      ],
    },
    education: {
      create: () => ({ degree: "", institution: "", location: "", from: "", to: "",
                       grade: "", details: "" }),
      head: (entry) => entry.degree || t("new.education"),
      fields: (entry, title) => [
        field(t("f.degree"), input(entry, "degree", { title, emptyTitle: t("new.education") })),
        el("div", { class: "grid2" }, [
          field(t("f.institution"), input(entry, "institution")),
          field(t("f.location"), input(entry, "location")),
        ]),
        el("div", { class: "grid3" }, [
          field(t("f.from"), dateControl(entry, "from")),
          field(t("f.to"), dateControl(entry, "to", { allowPresent: true })),
          field(t("f.grade"), input(entry, "grade", { placeholder: "1,3" })),
        ]),
        field(t("f.details"), input(entry, "details", { rows: 3 })),
      ],
    },
    projects: {
      create: () => ({ name: "", role: "", from: "", to: "", description: "", tech: [], link: "" }),
      head: (entry) => entry.name || t("new.project"),
      fields: (entry, title) => [
        field(t("f.name"), input(entry, "name", { title, emptyTitle: t("new.project") })),
        el("div", { class: "grid3" }, [
          field(t("f.role"), input(entry, "role")),
          field(t("f.from"), dateControl(entry, "from")),
          field(t("f.to"), dateControl(entry, "to", { allowPresent: true })),
        ]),
        field(t("f.description"), input(entry, "description", { rows: 3 })),
        field(t("f.tech"), tagList(entry, "tech", { addLabel: t("f.addTech") })),
        field(t("f.link"), input(entry, "link", { placeholder: "github.com/…" })),
      ],
    },
    publications: {
      create: () => ({ title: "", source: "", year: "", link: "" }),
      head: (entry) => entry.title || t("new.publication"),
      fields: (entry, title) => [
        field(t("f.pubTitle"), input(entry, "title", { title, emptyTitle: t("new.publication") })),
        el("div", { class: "grid2" }, [
          field(t("f.source"), input(entry, "source")),
          field(t("f.year"), yearControl(entry, "year")),
        ]),
        field(t("f.link"), input(entry, "link")),
      ],
    },
    languages: {
      create: () => ({ name: "", proficiency: "", level: 4 }),
      head: (entry) => entry.name || t("new.language"),
      fields: (entry, title) => {
        const dots = levels(entry);
        return [
          el("div", { class: "grid2" }, [
            field(t("f.language"), input(entry, "name", { title, emptyTitle: t("new.language") })),
            field(t("f.proficiency"), proficiencySelect(entry, dots)),
          ]),
          field("", dots),
        ];
      },
    },
    certificates: {
      create: () => ({ name: "", issuer: "", year: "" }),
      head: (entry) => entry.name || t("new.certificate"),
      fields: (entry, title) => [
        field(t("f.certName"), input(entry, "name", { title, emptyTitle: t("new.certificate") })),
        el("div", { class: "grid2" }, [
          field(t("f.issuer"), input(entry, "issuer")),
          field(t("f.year"), yearControl(entry, "year")),
        ]),
      ],
    },
  };
}

function listEditor(key) {
  const plan = LISTS()[key];
  const entries = DATA[key];
  const holder = el("div");
  const draw = () => {
    holder.textContent = "";
    entries.forEach((entry, index) => {
      const built = card(
        plan.head(entry),
        () => { entries.splice(index, 1); draw(); changed(); },
        (direction) => {
          const target = index + direction;
          if (target < 0 || target >= entries.length) return;
          [entries[index], entries[target]] = [entries[target], entries[index]];
          draw();
          changed();
        },
        []
      );
      built.node.append(...plan.fields(entry, built.title, index));
      holder.append(built.node);
    });
    holder.append(el("button", {
      class: "add", text: "+ " + t("add." + key),
      onclick: () => { entries.push(plan.create()); draw(); changed(); },
    }));
  };
  draw();
  return holder;
}

/* ------------------------------------------------------ special sections */

function personEditor() {
  const person = DATA.person;
  const image = el("img", { class: "photo-preview", src: person.photo || "", hidden: person.photo ? null : "" });
  const linkHolder = el("div");

  const drawLinks = () => {
    linkHolder.textContent = "";
    person.links.forEach((link, index) => {
      linkHolder.append(el("div", { class: "row" }, [
        input(link, "label", { placeholder: "GitHub" }),
        input(link, "url", { placeholder: "github.com/…" }),
        el("button", {
          class: "btn tiny", text: "×",
          onclick: () => { person.links.splice(index, 1); drawLinks(); changed(); },
        }),
      ]));
    });
    linkHolder.append(el("button", {
      class: "add", text: "+ " + t("f.addLink"),
      onclick: () => { person.links.push({ label: "", url: "" }); drawLinks(); changed(); },
    }));
  };
  drawLinks();

  const choosePhoto = () => {
    const picker = $("#file-photo");
    picker.value = "";
    picker.onchange = () => {
      const file = picker.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => shrink(reader.result, (small) => {
        person.photo = small;
        image.src = small;
        image.hidden = false;
        changed();
      });
      reader.readAsDataURL(file);
    };
    picker.click();
  };

  return [
    el("div", { class: "grid3" }, [
      field(t("f.firstName"), input(person, "firstName")),
      field(t("f.lastName"), input(person, "lastName")),
      field(t("f.title"), input(person, "title", { placeholder: "M.Sc." })),
    ]),
    field(t("f.position"), input(person, "position")),
    el("div", { class: "grid2" }, [
      field(t("f.email"), input(person, "email")),
      field(t("f.phone"), input(person, "phone")),
    ]),
    el("div", { class: "grid3" }, [
      field(t("f.location"), input(person, "location")),
      field(t("f.birthDate"), input(person, "birthDate", { placeholder: t("f.optional") })),
      field(t("f.nationality"), input(person, "nationality", { placeholder: t("f.optional") })),
    ]),
    field(t("f.links"), linkHolder),
    field(t("f.photo"), el("div", { class: "row" }, [
      image,
      el("button", { class: "btn tiny", text: t("f.chooseImage"), onclick: choosePhoto }),
      el("button", {
        class: "btn tiny", text: t("f.remove"),
        onclick: () => { person.photo = ""; image.hidden = true; changed(); },
      }),
    ])),
  ];
}

function shrink(dataUri, done) {
  const image = new Image();
  image.onload = () => {
    const max = 620;
    const factor = Math.min(1, max / Math.max(image.width, image.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(image.width * factor);
    canvas.height = Math.round(image.height * factor);
    canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
    done(canvas.toDataURL("image/jpeg", 0.86));
  };
  image.onerror = () => done(dataUri);
  image.src = dataUri;
}

function skillsEditor() {
  const holder = el("div");
  const draw = () => {
    holder.textContent = "";
    DATA.skills.forEach((groupData, index) => {
      const rows = el("div");
      const drawRows = () => {
        rows.textContent = "";
        groupData.items.forEach((item, itemIndex) => {
          rows.append(el("div", { class: "row" }, [
            input(item, "name", { placeholder: "Python" }),
            levels(item),
            el("button", {
              class: "btn tiny", text: "×",
              onclick: () => { groupData.items.splice(itemIndex, 1); drawRows(); changed(); },
            }),
          ]));
        });
        rows.append(el("button", {
          class: "add", text: "+ " + t("f.addSkill"),
          onclick: () => { groupData.items.push({ name: "", level: 4 }); drawRows(); focusLast(rows); changed(); },
        }));
      };
      drawRows();

      const built = card(
        groupData.category || t("new.category"),
        () => { DATA.skills.splice(index, 1); draw(); changed(); },
        (direction) => {
          const target = index + direction;
          if (target < 0 || target >= DATA.skills.length) return;
          [DATA.skills[index], DATA.skills[target]] = [DATA.skills[target], DATA.skills[index]];
          draw();
          changed();
        },
        []
      );
      built.node.append(
        field(t("f.category"), input(groupData, "category", { title: built.title, emptyTitle: t("new.category") })),
        rows
      );
      holder.append(built.node);
    });
    holder.append(
      el("button", {
        class: "add", text: "+ " + t("f.addCategory"),
        onclick: () => { DATA.skills.push({ category: "", items: [] }); draw(); changed(); },
      }),
      el("button", {
        class: "ai-btn", style: "margin-top:8px",
        text: "✦ " + t("ai.skills"),
        onclick: () => openAI("skills"),
      })
    );
  };
  draw();
  return holder;
}

function letterEditor() {
  const letter = DATA.letter;
  return [
    el("div", { class: "grid2" }, [
      field(t("l.company"), input(letter, "company")),
      field(t("l.contactName"), input(letter, "contactName")),
    ]),
    el("div", { class: "grid2" }, [
      field(t("l.street"), input(letter, "street")),
      field(t("l.city"), input(letter, "city")),
    ]),
    field(t("l.reference"), input(letter, "reference")),
    field(t("l.subject"), input(letter, "subject")),
    el("div", { class: "grid2" }, [
      field(t("l.senderCity"), input(letter, "senderCity",
        { placeholder: DATA.person.location || "" })),
      field(t("l.date"), input(letter, "date", { placeholder: t("f.optional") })),
    ]),
    field(t("l.salutation"), input(letter, "salutation", { placeholder: t("f.optional") })),
    field(t("l.body"), input(letter, "body", { rows: 10 })),
    el("div", { class: "hint", text: t("l.bodyHint") }),
    el("div", { class: "row", style: "margin:8px 0" }, [
      el("button", { class: "ai-btn", text: "✦ " + t("ai.letter"), onclick: () => openAI("letter") }),
      el("button", {
        class: "ai-btn", text: "✦ " + t("ai.proofread"),
        onclick: () => openAI("proofread", null, DATA.letter.body, "letterBody"),
      }),
    ]),
    field(t("l.closing"), input(letter, "closing", { placeholder: t("f.optional") })),
    field(t("l.attachments"), tagList(letter, "attachments",
      { placeholder: t("l.attachments"), addLabel: t("l.addAttachment") })),
  ];
}

function layoutEditor() {
  const meta = DATA.meta;
  const sections = el("div");
  const drawSections = () => {
    sections.textContent = "";
    meta.sections.forEach((section, index) => {
      const box = el("input", { type: "checkbox" });
      box.checked = section.enabled !== false;
      box.addEventListener("change", () => { section.enabled = box.checked; changed(); });

      const name = el("input", { class: "section-name" });
      name.value = section.title;
      name.addEventListener("input", () => { section.title = name.value; changed(); });

      const move = (direction) => {
        const target = index + direction;
        if (target < 0 || target >= meta.sections.length) return;
        [meta.sections[index], meta.sections[target]] = [meta.sections[target], meta.sections[index]];
        drawSections();
        changed();
      };

      sections.append(el("div", { class: "section-row" }, [
        box,
        name,
        select(section, "column", [
          { value: "main", name: t("col.main") },
          { value: "side", name: t("col.side") },
        ]),
        el("div", { class: "arrows" }, [
          el("button", { text: "▲", onclick: () => move(-1) }),
          el("button", { text: "▼", onclick: () => move(1) }),
        ]),
      ]));
    });
  };
  drawSections();

  const size = el("input", { type: "number", step: "0.2", min: "7.5", max: "12" });
  size.value = meta.fontSize;
  size.addEventListener("input", () => {
    meta.fontSize = parseFloat(size.value) || 9.6;
    changed();
  });

  return [
    el("div", { class: "grid2" }, [
      field(t("app.template"), select(meta, "template",
        INFO.templates.map((entry) => ({ value: entry.id, name: entry[language()] || entry.en })),
        () => { $("#template").value = meta.template; })),
      field(t("f.font"), select(meta, "font", INFO.fonts.map((f) => ({ value: f.id, name: f.name })))),
    ]),
    el("div", { class: "grid2" }, [
      field(t("f.fontSize"), size),
      field(t("app.density"), select(meta, "density", [
        { value: "tight", name: t("density.tight") },
        { value: "normal", name: t("density.normal") },
        { value: "airy", name: t("density.airy") },
      ], () => { $("#density").value = meta.density; })),
    ]),
    toggle(meta, "showLevels", t("f.showLevels")),
    toggle(meta, "pageNumbers", t("f.pageNumbers")),
    toggle(meta, "uppercaseHeadings", t("f.uppercase")),
    el("div", { class: "hint", text: t("f.sectionsHint") }),
    sections,
  ];
}

/* -------------------------------------------------------------- editor */

function renderEditor() {
  const editor = $("#editor");
  const open = new Set([...editor.querySelectorAll("details.group[open]")].map((d) => d.dataset.id));
  if (!open.size) open.add("person");
  editor.textContent = "";

  const parts = [
    ["person", group(t("group.person"), null, personEditor())],
    ["summary", group(t("group.summary"), null, [
      input(DATA, "summary", { rows: 5 }),
      el("div", { class: "row", style: "margin-top:8px" }, [
        el("button", { class: "ai-btn", text: "✦ " + t("ai.summary"), onclick: () => openAI("summary") }),
        el("button", {
          class: "ai-btn", text: "✦ " + t("ai.proofread"),
          onclick: () => openAI("proofread", null, DATA.summary),
        }),
      ]),
    ])],
  ];

  for (const key of ["experience", "education", "projects", "publications"]) {
    parts.push([key, group(t("group." + key), DATA[key].length, listEditor(key))]);
  }
  parts.push(["skills", group(t("group.skills"), DATA.skills.length, skillsEditor())]);
  for (const key of ["languages", "certificates"]) {
    parts.push([key, group(t("group." + key), DATA[key].length, listEditor(key))]);
  }
  parts.push(["interests", group(t("group.interests"), DATA.interests.length,
    tagList(DATA, "interests", { placeholder: t("f.interest"), addLabel: t("f.addInterest") }))]);
  parts.push(["letter", group(t("group.letter"), null, letterEditor())]);
  parts.push(["layout", group(t("group.layout"), null, layoutEditor())]);

  for (const [id, node] of parts) {
    node.dataset.id = id;
    if (open.has(id)) node.open = true;
    editor.append(node);
  }
}

/* ------------------------------------------------------------- preview */

function pageWidth() {
  if (fitMode) {
    const space = $("#pages").clientWidth - 46;
    return Math.max(320, Math.min(space, 1000));
  }
  return Math.round(A4_PIXELS * zoom);
}

function showZoom() {
  const width = pageWidth();
  $("#zoom-value").textContent = `${Math.round((width / A4_PIXELS) * 100)} %`;
  $("#pages").style.setProperty("--page-width", width + "px");
}

async function loadPreview() {
  if (previewAbort) previewAbort.abort();
  previewAbort = new AbortController();
  setStatus("status.rendering", "loading");
  try {
    const result = await api("/api/preview", {
      body: { data: DATA, scale: 1.7, doc: docKind },
      signal: previewAbort.signal,
    });
    const holder = $("#pages");
    holder.textContent = "";
    for (const source of result.pages) holder.append(el("img", { src: source, alt: "" }));
    showZoom();
    const word = result.pages.length === 1 ? t("preview.page") : t("preview.pages");
    $("#page-info").textContent = `${result.pages.length} ${word} · ${(result.size / 1024).toFixed(0)} kB`;
    setStatus("status.current");
  } catch (error) {
    if (error.name === "AbortError") return;
    setStatus("status.error", "error");
    toast(t("msg.previewFailed") + ": " + error.message, true);
  }
}

function changed() {
  applyAccent();
  clearTimeout(previewTimer);
  clearTimeout(saveTimer);
  setStatus("status.changed", "loading");
  previewTimer = setTimeout(loadPreview, 420);
  saveTimer = setTimeout(save, 1200);
}

async function save(notify = false) {
  try {
    await api("/api/data", { body: { data: DATA } });
    if (notify) toast(t("msg.saved") + ": " + INFO.file);
  } catch (error) {
    toast(t("msg.saveFailed") + ": " + error.message, true);
  }
}

/* --------------------------------------------------------------- colour */

function darken(hex, amount = 0.34) {
  const number = parseInt(hex.replace("#", ""), 16);
  const parts = [(number >> 16) & 255, (number >> 8) & 255, number & 255]
    .map((value) => Math.round(value * (1 - amount)));
  return "#" + parts.map((value) => value.toString(16).padStart(2, "0")).join("");
}

function applyAccent() {
  document.documentElement.style.setProperty("--accent", DATA.meta.accent);
  for (const swatch of document.querySelectorAll("#accents span")) {
    swatch.classList.toggle("active",
      swatch.dataset.color.toLowerCase() === DATA.meta.accent.toLowerCase()
      && swatch.dataset.dark.toLowerCase() === (DATA.meta.accentDark || "").toLowerCase());
  }
}

function setAccent(color, dark) {
  DATA.meta.accent = color;
  DATA.meta.accentDark = dark || darken(color);
  $("#accent-custom").value = color;
  changed();
}

/* ------------------------------------------------------------------- AI */

let aiAbort = null;
let ai = { action: null, index: null, kind: null, applicable: false, text: "",
           source: "", target: "summary" };

function providerNeedsKey(id) {
  const entry = (SETTINGS.providers || []).find((p) => p.id === id);
  return !!(entry && entry.needs_key);
}

function currentProvider() {
  return $("#ai-provider").value || SETTINGS.provider || "ollama";
}

function updateKeyField() {
  const provider = currentProvider();
  const needs = providerNeedsKey(provider);
  $("#key-field").hidden = !needs;
  if (!needs) return;
  const state = $("#key-state");
  if ((SETTINGS.key_from_env || {})[provider]) state.textContent = "· " + t("ai.keyFromEnv");
  else if ((SETTINGS.has_key || {})[provider]) state.textContent = "· " + t("ai.keyStored");
  else state.textContent = "";
  $("#ai-key").placeholder = t("ai.keyPlaceholder");
  $("#ai-key").value = "";
}

function fillProviders() {
  const node = $("#ai-provider");
  node.textContent = "";
  for (const entry of SETTINGS.providers) {
    node.append(el("option", { value: entry.id, text: entry.name }));
  }
  node.value = SETTINGS.provider || "ollama";
}

async function saveSettings(changes) {
  const result = await api("/api/settings", { body: changes });
  SETTINGS = result.settings;
  return SETTINGS;
}

async function loadModels() {
  const provider = currentProvider();
  const node = $("#ai-model");
  node.textContent = "";
  $("#ai-status").textContent = "…";
  try {
    const result = await api(`/api/models?provider=${encodeURIComponent(provider)}`);
    if (!result.models.length) {
      node.append(el("option", { value: "", text: t("ai.noModels") }));
      $("#ai-status").textContent = result.error ||
        (providerNeedsKey(provider) && !(SETTINGS.has_key || {})[provider] ? t("ai.noKey") : t("ai.noModels"));
      return;
    }
    for (const entry of result.models) {
      node.append(el("option", {
        value: entry.id,
        text: entry.note ? `${entry.name} · ${entry.note}` : entry.name,
      }));
    }
    const remembered = (SETTINGS.models || {})[provider];
    if (remembered && result.models.some((m) => m.id === remembered)) node.value = remembered;
    $("#ai-status").textContent = `${result.models.length} ${t("ai.modelsAvailable")}`;
  } catch (error) {
    node.append(el("option", { value: "", text: t("ai.noModels") }));
    $("#ai-status").textContent = error.message;
  }
}

function restoreDocKindButtons() {
  for (const button of document.querySelectorAll("#docs button")) {
    button.classList.toggle("active", button.dataset.doc === docKind);
  }
  store.set("cvboreout.doc", docKind);
}

function restoreDocKind() {
  docKind = store.get("cvboreout.doc", "resume");
  restoreDocKindButtons();
}

function showAI(visible) {
  $("#ai").hidden = !visible;
  document.body.classList.toggle("ai-open", visible);
  showZoom();
}

function openAI(action = null, index = null, text = null, target = "summary") {
  showAI(true);
  fillStations();
  if (index !== null) $("#ai-station").value = String(index);
  if (action) {
    ai.target = target;
    if (text !== null) ai.source = text;
    chooseAction(action);
    runAI();
  }
}

function chooseAction(action) {
  ai.action = action;
  for (const button of document.querySelectorAll(".ai-actions button")) {
    button.classList.toggle("active", button.dataset.action === action);
  }
  $("#station-field").hidden = action !== "bullets";
  $("#free-field").hidden = action !== "free";
}

function fillStations() {
  const node = $("#ai-station");
  const previous = node.value;
  node.textContent = "";
  DATA.experience.forEach((entry, index) => {
    node.append(el("option", {
      value: String(index),
      text: `${entry.position || t("new.experience")} – ${entry.company || ""}`,
    }));
  });
  if (previous) node.value = previous;
}

async function runAI() {
  const provider = currentProvider();
  const model = $("#ai-model").value;
  if (!model) return toast(t("ai.needModel"), true);
  const action = ai.action;
  if (!action) return;

  const options = {
    posting: $("#ai-posting").value,
    index: parseInt($("#ai-station").value || "0", 10),
    text: action === "free" ? $("#ai-free").value : (ai.source || ""),
  };
  if (action === "free" && !options.text.trim()) return toast(t("ai.needInstruction"), true);
  if (action === "match" && !options.posting.trim()) return toast(t("ai.needPosting"), true);

  ai.index = options.index;
  ai.text = "";
  $("#ai-text").value = "";
  $("#ai-apply").disabled = true;
  $("#ai-copy").disabled = true;
  $("#ai-stop").hidden = false;
  $("#ai-status").textContent = `${model} ${t("ai.thinking")}`;

  aiAbort = new AbortController();
  try {
    const response = await fetch("/api/ai", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Token": TOKEN },
      body: JSON.stringify({ action, provider, model, data: DATA, options }),
      signal: aiAbort.signal,
    });
    if (!response.ok) throw new Error((await response.json()).error || response.statusText);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop();
      for (const block of blocks) {
        const event = (block.match(/^event: (.*)$/m) || [])[1];
        const payload = JSON.parse((block.match(/^data: (.*)$/m) || [, "{}"])[1]);
        if (event === "start") {
          ai.kind = payload.kind;
          ai.applicable = payload.applicable;
        } else if (event === "token") {
          ai.text += payload.t;
          const output = $("#ai-text");
          output.value = ai.text;
          output.scrollTop = output.scrollHeight;
        } else if (event === "error") {
          throw new Error(payload.message);
        }
      }
    }
    $("#ai-status").textContent = t("ai.done");
    $("#ai-apply").disabled = !ai.applicable;
    $("#ai-copy").disabled = false;
    if (model) saveSettings({ provider, model }).catch(() => {});
  } catch (error) {
    if (error.name !== "AbortError") {
      $("#ai-status").textContent = t("status.error");
      toast("KI: " + error.message, true);
    }
  } finally {
    $("#ai-stop").hidden = true;
  }
}

function applyAI() {
  const text = $("#ai-text").value.trim();
  if (!text) return;
  const lines = () => text.split("\n")
    .map((line) => line.replace(/^\s*(?:[-•*–—]|\d+[.)])\s*/, "").trim())
    .filter(Boolean);

  if (ai.kind === "letter") {
    DATA.letter.body = text;
    docKind = "letter";
    restoreDocKindButtons();
  } else if (ai.kind === "bullets") {
    const entry = DATA.experience[ai.index];
    if (!entry) return;
    entry.bullets = lines();
  } else if (ai.kind === "skills") {
    const groups = [];
    for (const line of lines()) {
      const separator = line.indexOf(":");
      if (separator < 1) continue;
      const items = line.slice(separator + 1).split(",").map((s) => s.trim()).filter(Boolean);
      if (items.length) {
        groups.push({
          category: line.slice(0, separator).trim(),
          items: items.map((name) => ({ name, level: 4 })),
        });
      }
    }
    if (!groups.length) return toast(t("ai.unreadable"), true);
    DATA.skills = groups;
  } else if (ai.target === "letterBody") {
    DATA.letter.body = text;
  } else {
    DATA.summary = text;
  }
  renderEditor();
  changed();
  toast(t("msg.applied"));
}

/* --------------------------------------------------------------- topbar */

function fillTopbar() {
  const template = $("#template");
  template.textContent = "";
  for (const entry of INFO.templates) {
    template.append(el("option", { value: entry.id, text: entry[language()] || entry.en }));
  }
  template.value = DATA.meta.template;

  const languages = $("#language");
  languages.textContent = "";
  for (const entry of INFO.languages) {
    languages.append(el("option", { value: entry.id, text: entry.name }));
  }
  languages.value = language();

  const accents = $("#accents");
  accents.textContent = "";
  for (const entry of INFO.accents) {
    // Two-tone swatch: the accent itself plus the band colour it comes with.
    accents.append(el("span", {
      style: `background:linear-gradient(135deg, ${entry.color} 0 50%, ${entry.dark} 50% 100%)`,
      title: entry.name,
      "data-color": entry.color,
      "data-dark": entry.dark,
      onclick: () => setAccent(entry.color, entry.dark),
    }));
  }
  $("#accent-custom").value = DATA.meta.accent;
  $("#density").value = DATA.meta.density;
}

async function switchLanguage(target) {
  DATA = await api("/api/language", { body: { data: DATA, language: target } });
  translateStatic();
  fillTopbar();
  renderEditor();
  updateKeyField();
  chooseAction(ai.action);
  changed();
}

async function exportPdf() {
  setStatus("status.exporting", "loading");
  try {
    const result = await api("/api/pdf", { body: { data: DATA, doc: docKind } });
    setStatus("status.current");
    if (result.cancelled) return;
    toast(t("msg.exported") + ": " + result.path);
  } catch (error) {
    setStatus("status.error", "error");
    toast(t("msg.exportFailed") + ": " + error.message, true);
  }
}

function saveJson() {
  const blob = new Blob([JSON.stringify(DATA, null, 2)], { type: "application/json" });
  const link = el("a", { href: URL.createObjectURL(blob), download: "resume.json" });
  document.body.append(link);
  link.click();
  link.remove();
  toast(t("msg.downloaded"));
}

function loadJson() {
  const picker = $("#file-json");
  picker.value = "";
  picker.onchange = () => {
    const file = picker.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        DATA = JSON.parse(reader.result);
        rebuild();
        toast(t("msg.loaded") + ": " + file.name);
      } catch (error) {
        toast(t("msg.invalidJson"), true);
      }
    };
    reader.readAsText(file);
  };
  picker.click();
}

function rebuild() {
  translateStatic();
  fillTopbar();
  renderEditor();
  applyAccent();
  changed();
}

/* ---------------------------------------------------------------- start */

function makeHandle(selector, variable, measure, storeKey) {
  const handle = $(selector);
  if (!handle) return;
  const remembered = parseInt(store.get(storeKey, "0"), 10);
  if (remembered) document.documentElement.style.setProperty(variable, remembered + "px");

  let active = false;
  const stop = () => {
    if (!active) return;
    active = false;
    document.body.classList.remove("dragging");
    store.set(storeKey, parseInt(
      getComputedStyle(document.documentElement).getPropertyValue(variable), 10) || 0);
    showZoom();
  };
  handle.addEventListener("mousedown", (event) => {
    event.preventDefault();
    active = true;
    document.body.classList.add("dragging");
  });
  window.addEventListener("mouseup", stop);
  window.addEventListener("mouseleave", stop);
  window.addEventListener("mousemove", (event) => {
    if (!active) return;
    document.documentElement.style.setProperty(variable, measure(event) + "px");
    showZoom();
  });
}

function makeHandles() {
  makeHandle("#handle", "--editor-width",
    (event) => Math.max(330, Math.min(event.clientX, window.innerWidth - 320)),
    "cvboreout.editorWidth");
  makeHandle("#ai-handle", "--ai-width",
    (event) => Math.max(320, Math.min(window.innerWidth - event.clientX, window.innerWidth - 420)),
    "cvboreout.aiWidth");
}

function bindEvents() {
  $("#template").addEventListener("change", (event) => {
    DATA.meta.template = event.target.value;
    renderEditor();
    changed();
  });
  $("#density").addEventListener("change", (event) => {
    DATA.meta.density = event.target.value;
    changed();
  });
  $("#language").addEventListener("change", (event) => switchLanguage(event.target.value));
  $("#accent-custom").addEventListener("input", (event) => setAccent(event.target.value));

  $("#btn-pdf").addEventListener("click", exportPdf);
  $("#btn-ai").addEventListener("click", () => { showAI($("#ai").hidden); fillStations(); });
  $("#ai-close").addEventListener("click", () => showAI(false));
  $("#ai-reload").addEventListener("click", loadModels);
  $("#ai-provider").addEventListener("change", async (event) => {
    await saveSettings({ provider: event.target.value });
    updateKeyField();
    loadModels();
  });
  $("#ai-key-save").addEventListener("click", async () => {
    await saveSettings({ provider: currentProvider(), key: $("#ai-key").value });
    updateKeyField();
    toast(t("msg.keySaved"));
    loadModels();
  });
  $("#ai-model").addEventListener("change", (event) =>
    saveSettings({ provider: currentProvider(), model: event.target.value }).catch(() => {}));
  $("#ai-apply").addEventListener("click", applyAI);
  $("#ai-copy").addEventListener("click", () => copyText($("#ai-text").value));
  $("#ai-stop").addEventListener("click", () => aiAbort && aiAbort.abort());
  for (const button of document.querySelectorAll(".ai-actions button")) {
    button.addEventListener("click", () => {
      ai.target = "summary";
      if (button.dataset.action === "proofread") ai.source = DATA.summary;
      chooseAction(button.dataset.action);
      runAI();
    });
  }

  $("#ai-posting").value = store.get("cvboreout.posting");
  $("#ai-posting").addEventListener("input", (event) =>
    store.set("cvboreout.posting", event.target.value));

  $("#btn-menu").addEventListener("click", (event) => {
    event.stopPropagation();
    $("#menu").hidden = !$("#menu").hidden;
  });
  document.addEventListener("click", () => ($("#menu").hidden = true));
  for (const button of document.querySelectorAll("#menu button")) {
    button.addEventListener("click", async () => {
      const action = button.dataset.menu;
      if (action === "save") await save(true);
      if (action === "json-save") saveJson();
      if (action === "json-load") loadJson();
      if (action === "sample") { DATA = await api("/api/sample"); rebuild(); }
      if (action === "clear" && confirm(t("msg.confirmClear"))) {
        DATA = await api("/api/blank");
        rebuild();
      }
    });
  }

  for (const button of document.querySelectorAll("#docs button")) {
    button.addEventListener("click", () => {
      docKind = button.dataset.doc;
      for (const other of document.querySelectorAll("#docs button")) {
        other.classList.toggle("active", other === button);
      }
      store.set("cvboreout.doc", docKind);
      loadPreview();
    });
  }

  const stepZoom = (step) => {
    if (fitMode) zoom = pageWidth() / A4_PIXELS;
    fitMode = false;
    zoom = Math.max(0.4, Math.min(2.5, zoom + step));
    showZoom();
  };
  $("#zoom-in").addEventListener("click", () => stepZoom(0.1));
  $("#zoom-out").addEventListener("click", () => stepZoom(-0.1));
  $("#zoom-fit").addEventListener("click", () => { fitMode = true; showZoom(); });
  window.addEventListener("resize", showZoom);
  $("#pages").addEventListener("wheel", (event) => {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    stepZoom(-Math.sign(event.deltaY) * 0.08);
  }, { passive: false });

  document.addEventListener("keydown", (event) => {
    if (!(event.ctrlKey || event.metaKey)) return;
    if (event.key === "s") { event.preventDefault(); save(true); }
    if (event.key === "e") { event.preventDefault(); exportPdf(); }
  });
}

async function start() {
  try {
    INFO = await api("/api/status");
    SETTINGS = INFO.settings;
    DATA = await api("/api/data");
  } catch (error) {
    document.body.innerHTML = `<p style="padding:40px">Start failed: ${error.message}</p>`;
    return;
  }
  for (const [name, step] of [
    ["Translation", translateStatic],
    ["Topbar", fillTopbar],
    ["Providers", fillProviders],
    ["Keys", updateKeyField],
    ["Events", bindEvents],
    ["Handles", makeHandles],
    ["Editor", renderEditor],
    ["Accent", applyAccent],
    ["Zoom", showZoom],
    ["Document", restoreDocKind],
  ]) {
    try {
      step();
    } catch (error) {
      console.error(name, error);
      toast(`${name}: ${error.message}`, true);
    }
  }
  loadModels();
  loadPreview();
}

window.addEventListener("error", (event) => {
  console.error(event.error || event.message);
  toast("Error: " + event.message, true);
});

start();
