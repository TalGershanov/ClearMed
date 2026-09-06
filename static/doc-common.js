/* Shared between static/script.js (desktop wizard, step 4) and
   static/mobile-doc.js (the /doc/<uuid> QR landing page) -- both target the
   exact same #doc-* element ids by design, so the language dropdown's
   widget and the doc-content render can be shared verbatim. */

const ORIGINAL_LANGUAGE_LABEL = "Original";

function renderDocFields(explanationText, explainedTermsList, disclaimer) {
	const explanationEl = document.getElementById("doc-explanation");
	explanationEl.innerHTML = "";
	const p = document.createElement("p");
	p.setAttribute("dir", "auto");
	p.textContent = explanationText;
	explanationEl.appendChild(p);

	const listEl = document.getElementById("doc-terms-list");
	listEl.innerHTML = "";
	explainedTermsList.forEach((term) => {
		const li = document.createElement("li");
		li.textContent = term;
		listEl.appendChild(li);
	});

	if (disclaimer) {
		const disclaimerEl = document.getElementById("doc-disclaimer");
		if (disclaimerEl) disclaimerEl.textContent = disclaimer;
	}
}

/* Wires a text input + a following <ul> into a click-to-select combobox:
   click/focus shows the full language list, typing filters it live, and
   clicking an option applies immediately -- no Enter, no blur required.
   Native <input list>/<datalist> was tried first but doesn't render a
   usable dropdown on mobile Safari and only commits on `change` (blur/
   Enter), which is exactly what this replaces.
   onSelect(code) fires on click: code is null for "Original", else the
   selected language's code. */
async function initLanguageDropdown(inputEl, listEl, onSelect) {
	let languages = []; // [{name, code}]
	let lastCommittedValue = ORIGINAL_LANGUAGE_LABEL;

	function renderList(filterText) {
		const trimmed = filterText.trim().toLowerCase();
		listEl.innerHTML = "";

		const originalLi = document.createElement("li");
		originalLi.textContent = ORIGINAL_LANGUAGE_LABEL;
		originalLi.dataset.code = "";
		listEl.appendChild(originalLi);

		languages
			.filter((lang) => lang.name.toLowerCase().includes(trimmed))
			.forEach((lang) => {
				const li = document.createElement("li");
				li.textContent = lang.name;
				li.dataset.code = lang.code;
				listEl.appendChild(li);
			});
	}

	function openList() {
		renderList(inputEl.value === lastCommittedValue ? "" : inputEl.value);
		listEl.classList.remove("hidden");
	}

	function closeList() {
		listEl.classList.add("hidden");
	}

	inputEl.addEventListener("focus", openList);
	// A selection's mousedown handler below calls preventDefault() so the
	// input never blurs on selection -- which means typing again right
	// after a selection won't get a fresh `focus` event to reopen the list.
	// Re-show it here too, not just re-filter, so that still works.
	inputEl.addEventListener("input", () => {
		renderList(inputEl.value);
		listEl.classList.remove("hidden");
	});

	// mousedown, not click: fires (and can preventDefault) before the
	// input's own blur, so the selection is captured before an outside-click
	// handler could hide the list out from under it -- the standard fix for
	// the combobox click-vs-blur race, and it works the same way for touch
	// (iOS synthesizes mousedown from touchstart).
	listEl.addEventListener("mousedown", (e) => {
		const li = e.target.closest("li");
		if (!li) return;
		e.preventDefault();
		const code = li.dataset.code === "" ? null : li.dataset.code;
		inputEl.value = li.textContent;
		lastCommittedValue = li.textContent;
		closeList();
		onSelect(code);
	});

	document.addEventListener("mousedown", (e) => {
		if (e.target === inputEl || listEl.contains(e.target)) return;
		inputEl.value = lastCommittedValue;
		closeList();
	});

	try {
		const res = await fetch("/languages");
		if (!res.ok) throw new Error(`Server returned ${res.status}`);
		languages = await res.json();
	} catch (err) {
		console.error("Could not load supported languages", err);
	}
}
