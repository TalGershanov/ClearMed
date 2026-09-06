const shareId = location.pathname.split("/").filter(Boolean).pop();

const statusEl = document.getElementById("mobile-status");
const docWrapEl = document.getElementById("mobile-doc-wrap");
const docLanguageInput = document.getElementById("doc-language-input");
const docLanguageList = document.getElementById("doc-language-list");

let originalDocument = null;

function showError(message) {
	statusEl.querySelector(".card-subtitle").textContent = message;
	statusEl.classList.remove("hidden");
	docWrapEl.classList.add("hidden");
}

function showDocument() {
	document.getElementById("doc-date").textContent = new Date().toLocaleDateString("en-US", {
		year: "numeric",
		month: "long",
		day: "numeric",
	});
	statusEl.classList.add("hidden");
	docWrapEl.classList.remove("hidden");
	renderDocFields(originalDocument.explanation_text, originalDocument.explained_terms_list, originalDocument.disclaimer);
}

async function loadDocument() {
	try {
		const res = await fetch(`/shares/${shareId}`);
		if (res.status === 404) {
			showError("This document link is no longer valid.");
			return;
		}
		if (!res.ok) throw new Error(`Server returned ${res.status}`);
		originalDocument = await res.json();
		showDocument();
	} catch (err) {
		console.error(err);
		showError("Could not load this document. Please try again.");
	}
}

initLanguageDropdown(docLanguageInput, docLanguageList, async (code) => {
	if (code === null) {
		renderDocFields(originalDocument.explanation_text, originalDocument.explained_terms_list, originalDocument.disclaimer);
		return;
	}
	try {
		const res = await fetch(`/shares/${shareId}/translate`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ target_language_code: code }),
		});
		if (res.status === 404) {
			showError("This document link is no longer valid.");
			return;
		}
		if (!res.ok) throw new Error(`Server returned ${res.status}`);
		const data = await res.json();
		renderDocFields(data.explanation_text, data.explained_terms_list, data.disclaimer);
	} catch (err) {
		console.error(err);
		alert("Could not translate the document. Please try again.");
	}
});

document.getElementById("btn-print").addEventListener("click", () => {
	window.print();
});

loadDocument();
