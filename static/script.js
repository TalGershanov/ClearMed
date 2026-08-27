const STEP_TITLES = {
	1: "Medical Document Input",
	2: "Medical Terms Detected",
	3: "Patient-Friendly Summary",
	4: "Confirmation & Export",
};

const state = {
	currentStep: 1,
	fileName: "",
	originalText: "",
	detectedTerms: [],
	uiSelection: {},
	translatedText: "",
	explainedTermsList: [],
};

const el = (id) => document.getElementById(id);

function goToStep(step) {
	state.currentStep = step;
	for (let i = 1; i <= 4; i++) {
		el(`panel-${i}`).classList.toggle("hidden", i !== step);
	}
	el("step-badge").textContent = step;
	el("step-title").textContent = STEP_TITLES[step];

	document.querySelectorAll("#progress-steps li").forEach((li) => {
		const liStep = Number(li.dataset.step);
		li.classList.toggle("done", liStep < step);
		li.classList.toggle("current", liStep === step);
	});

	window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ---------- Step 1: file upload ---------- */

const uploadBox = el("upload-box");
const fileInput = el("file-input");
const cameraInput = el("camera-input");
const btnIdentify = el("btn-identify");
const photoReview = el("photo-review");
const photoReviewBox = el("photo-review-box");

uploadBox.addEventListener("dragover", (e) => {
	e.preventDefault();
	uploadBox.classList.add("dragover");
});

uploadBox.addEventListener("dragleave", () => {
	uploadBox.classList.remove("dragover");
});

uploadBox.addEventListener("drop", (e) => {
	e.preventDefault();
	uploadBox.classList.remove("dragover");
	if (e.dataTransfer.files.length) {
		handleFile(e.dataTransfer.files[0]);
	}
});

fileInput.addEventListener("change", () => {
	if (fileInput.files.length) {
		handleFile(fileInput.files[0]);
	}
});

cameraInput.addEventListener("change", () => {
	if (cameraInput.files.length) {
		handleFile(cameraInput.files[0]);
	}
});

async function handleFile(file) {
	const name = file.name.toLowerCase();
	btnIdentify.disabled = true;
	el("upload-box-filename").textContent = "Reading file…";

	const isImage = file.type.startsWith("image/");
	photoReview.classList.add("hidden");

	try {
		let text;
		if (isImage) {
			text = await readImageAsText(file);
		} else if (name.endsWith(".pdf")) {
			text = await readPdfAsText(file);
		} else {
			text = await readTextFile(file);
		}
		state.originalText = text.trim();
		state.fileName = file.name;
		el("upload-box-filename").textContent = file.name;
		btnIdentify.disabled = state.originalText.length === 0;
		if (state.originalText.length === 0) {
			el("upload-box-filename").textContent = `${file.name} (no text found)`;
		} else if (isImage) {
			photoReviewBox.value = state.originalText;
			photoReview.classList.remove("hidden");
		}
	} catch (err) {
		console.error(err);
		el("upload-box-filename").textContent = `Could not read ${file.name}`;
		btnIdentify.disabled = true;
	}
}

photoReviewBox.addEventListener("input", () => {
	state.originalText = photoReviewBox.value.trim();
	btnIdentify.disabled = state.originalText.length === 0;
});

function readTextFile(file) {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(reader.result);
		reader.onerror = () => reject(reader.error);
		reader.readAsText(file);
	});
}

async function readImageAsText(file) {
	el("upload-box-filename").textContent = "Reading photo…";
	const formData = new FormData();
	formData.append("image", file);
	const res = await fetch("/ocr", { method: "POST", body: formData });
	if (!res.ok) throw new Error(`Server returned ${res.status}`);
	const { text } = await res.json();
	return text;
}

async function readPdfAsText(file) {
	pdfjsLib.GlobalWorkerOptions.workerSrc =
		"https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
	const buffer = await file.arrayBuffer();
	const pdf = await pdfjsLib.getDocument({ data: buffer }).promise;
	let text = "";
	for (let i = 1; i <= pdf.numPages; i++) {
		const page = await pdf.getPage(i);
		const content = await page.getTextContent();
		text += content.items.map((item) => item.str).join(" ") + "\n";
	}
	return text;
}

btnIdentify.addEventListener("click", async () => {
	btnIdentify.disabled = true;
	btnIdentify.textContent = "Analysing…";
	try {
		const res = await fetch("/analyse", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ text: state.originalText }),
		});
		if (!res.ok) throw new Error(`Server returned ${res.status}`);
		const data = await res.json();
		state.detectedTerms = data.detected_terms || [];
		state.uiSelection = data.ui_selection || {};
		renderTermsTable();
		goToStep(2);
	} catch (err) {
		console.error(err);
		alert("Could not analyse the document. Please try again.");
	} finally {
		btnIdentify.disabled = false;
		btnIdentify.textContent = "Identify Medical Terms →";
	}
});

/* ---------- Step 2: select terms ---------- */

function renderTermsTable() {
	const tbody = el("terms-tbody");
	tbody.innerHTML = "";

	state.detectedTerms.forEach((term) => {
		const checked = state.uiSelection[term.main_term] !== false;
		const tr = document.createElement("tr");
		tr.innerHTML = `
			<td class="col-check"><input type="checkbox" data-term="${escapeHtml(term.main_term)}" ${checked ? "checked" : ""}></td>
			<td class="term-name">${escapeHtml(term.main_term)}</td>
			<td>${escapeHtml(term.short_explanation || "")}</td>
		`;
		tbody.appendChild(tr);
	});

	el("check-all").checked = true;
}

el("check-all").addEventListener("change", (e) => {
	document.querySelectorAll("#terms-tbody input[type=checkbox]").forEach((cb) => {
		cb.checked = e.target.checked;
	});
});

el("btn-back-2").addEventListener("click", () => goToStep(1));

el("btn-generate").addEventListener("click", async () => {
	const btn = el("btn-generate");
	const uiSelection = {};
	document.querySelectorAll("#terms-tbody input[type=checkbox]").forEach((cb) => {
		uiSelection[cb.dataset.term] = cb.checked;
	});
	state.uiSelection = uiSelection;

	btn.disabled = true;
	btn.textContent = "Generating…";
	try {
		const res = await fetch("/translate", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ text: state.originalText, ui_selection: uiSelection }),
		});
		if (!res.ok) throw new Error(`Server returned ${res.status}`);
		const data = await res.json();
		state.translatedText = data.translated_text || "";
		state.explainedTermsList = data.explained_terms_list || [];
		renderSummary();
		goToStep(3);
	} catch (err) {
		console.error(err);
		alert("Could not generate the summary. Please try again.");
	} finally {
		btn.disabled = false;
		btn.textContent = "Generate Simplified Summary →";
	}
});

/* ---------- Step 3: summary ---------- */

function renderSummary() {
	const box = el("explanation-box");
	box.contentEditable = "false";
	el("btn-edit-manually").textContent = "✎ Edit manually";
	box.innerHTML = "";
	sentencesOf(state.translatedText).forEach((sentence) => {
		const p = document.createElement("p");
		p.textContent = sentence;
		box.appendChild(p);
	});

	el("original-box").textContent = state.originalText;

	const list = el("detected-list");
	list.innerHTML = "";
	state.explainedTermsList.forEach((term) => {
		const li = document.createElement("li");
		li.textContent = term;
		list.appendChild(li);
	});
}

function sentencesOf(text) {
	const parts = text.match(/[^.!?]+[.!?]*[)"']*/g);
	return parts ? parts.map((s) => s.trim()).filter(Boolean) : [text];
}

el("btn-edit-manually").addEventListener("click", () => {
	const box = el("explanation-box");
	const editing = box.contentEditable === "true";
	box.contentEditable = editing ? "false" : "true";
	el("btn-edit-manually").textContent = editing ? "✎ Edit manually" : "✓ Done editing";
	if (editing) {
		state.translatedText = box.innerText;
	} else {
		box.focus();
	}
});

el("btn-back-3").addEventListener("click", () => goToStep(2));
el("btn-approve").addEventListener("click", () => {
	renderExportDoc();
	goToStep(4);
});

/* ---------- Step 4: export ---------- */

function renderExportDoc() {
	el("doc-date").textContent = new Date().toLocaleDateString("en-US", {
		year: "numeric",
		month: "long",
		day: "numeric",
	});

	const explanation = el("doc-explanation");
	explanation.innerHTML = "";
	sentencesOf(state.translatedText).forEach((sentence) => {
		const p = document.createElement("p");
		p.textContent = sentence;
		explanation.appendChild(p);
	});

	el("doc-original-text").textContent = state.originalText;

	const list = el("doc-terms-list");
	list.innerHTML = "";
	state.explainedTermsList.forEach((term) => {
		const li = document.createElement("li");
		li.textContent = term;
		list.appendChild(li);
	});
}

el("btn-print").addEventListener("click", () => {
	window.print();
});

el("btn-new-doc").addEventListener("click", () => {
	state.currentStep = 1;
	state.fileName = "";
	state.originalText = "";
	state.detectedTerms = [];
	state.uiSelection = {};
	state.translatedText = "";
	state.explainedTermsList = [];

	fileInput.value = "";
	cameraInput.value = "";
	photoReviewBox.value = "";
	photoReview.classList.add("hidden");
	el("upload-box-filename").textContent = "";
	btnIdentify.disabled = true;

	goToStep(1);
});

function escapeHtml(str) {
	const div = document.createElement("div");
	div.textContent = str;
	return div.innerHTML;
}

goToStep(1);
