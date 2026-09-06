/* Shared between static/script.js (desktop wizard, step 4) and
   static/mobile-doc.js (the /doc/<uuid> QR landing page) -- both target the
   exact same #doc-* element ids by design, so the language dropdown's
   population/lookup and the doc-content render can be shared verbatim. */

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

async function loadLanguageOptions(datalistEl) {
	datalistEl.innerHTML = `<option value="${ORIGINAL_LANGUAGE_LABEL}">`;
	try {
		const res = await fetch("/languages");
		if (!res.ok) throw new Error(`Server returned ${res.status}`);
		const languages = await res.json();
		languages.forEach((lang) => {
			const option = document.createElement("option");
			option.value = lang.name;
			option.dataset.code = lang.code;
			datalistEl.appendChild(option);
		});
	} catch (err) {
		console.error("Could not load supported languages", err);
	}
}

function resolveLanguageCode(datalistEl, typedValue) {
	const trimmed = typedValue.trim();
	if (trimmed === "" || trimmed === ORIGINAL_LANGUAGE_LABEL) {
		return null;
	}
	const match = Array.from(datalistEl.options).find((opt) => opt.value === trimmed);
	return match ? match.dataset.code : undefined;
}
