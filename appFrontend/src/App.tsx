import { useEffect, useState } from "react";
import { fetchCurrentUser, login as loginRequest, logout as logoutRequest } from "@/api/auth";
import { analyseDocument, fetchDocument, simplifyDocument, updateTermSelection, uploadDocument } from "@/api/documents";
import { createFolder as createFolderRequest, fetchFolder, fetchRootFolders } from "@/api/folders";
import { AppBar } from "@/components/AppBar";
import { BottomNav } from "@/components/BottomNav";
import { DocumentDetailScreen } from "@/screens/DocumentDetailScreen";
import { FolderScreen } from "@/screens/FolderScreen";
import { LibraryScreen } from "@/screens/LibraryScreen";
import { LoginScreen } from "@/screens/LoginScreen";
import TermsFoundScreen from "@/screens/TermsFoundScreen";
import { UploadScreen } from "@/screens/UploadScreen";
import type { ApiDocument, ApiDocumentDetail, ApiFolder, ApiFolderDetail, ApiUser, Doc, Screen } from "@/types";

// Search-only mock data (Library screen search box). No backend document
// search exists yet -- this is intentionally unconnected to real uploads.
const USER_DOCS: Record<string, Doc[]> = {
  "demo@example.com": [
    { id: "1", name: "Blood Panel – June 2025",    folder: "Lab Results",   date: "Jun 12, 2025", type: "PDF", translated: true },
    { id: "2", name: "Chest X-Ray Report",          folder: "Imaging",       date: "May 3, 2025",  type: "Scan" },
    { id: "3", name: "Metformin Prescription",      folder: "Prescriptions", date: "Apr 18, 2025", type: "PDF", translated: true },
    { id: "4", name: "Knee MRI Analysis",           folder: "Imaging",       date: "Mar 29, 2025", type: "Scan" },
    { id: "5", name: "Post-Op Instructions",        folder: "Surgery",       date: "Feb 7, 2025",  type: "PDF" },
    { id: "6", name: "Annual Check-Up Summary",     folder: "General",       date: "Jan 15, 2025", type: "PDF", translated: true },
  ],
};

function getUserDocs(email: string): Doc[] {
  return USER_DOCS[email] ?? [];
}

// ─── App shell ────────────────────────────────────────────────────────────────
export default function App() {
  const [screen, setScreen] = useState<Screen>("login");
  const [currentUser, setCurrentUser] = useState<ApiUser | null>(null);
  // navPath = folders from root to current, each with its real backend id
  const [navPath, setNavPath] = useState<{ id: number; name: string }[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<ApiDocument | null>(null);
  const [selectedDocDetail, setSelectedDocDetail] = useState<ApiDocumentDetail | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [rootFolders, setRootFolders] = useState<ApiFolder[]>([]);
  const [currentFolder, setCurrentFolder] = useState<ApiFolderDetail | null>(null);

  async function loadRootFolders() {
    try {
      setRootFolders(await fetchRootFolders());
    } catch {
      // best-effort refresh -- UI just keeps showing the last known list
    }
  }

  async function loadFolder(id: number) {
    try {
      setCurrentFolder(await fetchFolder(id));
    } catch {
      // best-effort -- the user can navigate back and retry
    }
  }

  // Restores an existing session on page load/refresh if the auth cookie is
  // still valid, so uploaded documents/created folders are visible again
  // without logging in again.
  useEffect(() => {
    (async () => {
      try {
        const user = await fetchCurrentUser();
        setCurrentUser(user);
        setDocs(getUserDocs(user.email));
        setScreen("library");
        await loadRootFolders();
      } catch {
        // no valid session -- stay on the login screen
      }
    })();
  }, []);

  async function login(email: string, password: string) {
    const user = await loginRequest(email, password);
    setCurrentUser(user);
    setDocs(getUserDocs(user.email));
    setNavPath([]);
    setScreen("library");
    await loadRootFolders();
  }

  async function logout() {
    try {
      await logoutRequest();
    } catch {
      // clear local state regardless of whether the network call succeeded
    }
    setScreen("login");
    setCurrentUser(null);
    setNavPath([]);
    setSelectedDoc(null);
    setSelectedDocDetail(null);
    setDocs([]);
    setRootFolders([]);
    setCurrentFolder(null);
  }

  async function createRootFolder(name: string, color: string) {
    await createFolderRequest(name, color, null);
    await loadRootFolders();
  }

  async function createChildFolder(name: string, color: string) {
    if (!currentFolder) return;
    await createFolderRequest(name, color, currentFolder.id);
    await loadFolder(currentFolder.id);
  }

  async function drillInto(folder: ApiFolder) {
    setNavPath(prev => [...prev, { id: folder.id, name: folder.name }]);
    setScreen("folder");
    setCurrentFolder(null);
    await loadFolder(folder.id);
  }

  async function navigateTo(depth: number) {
    // depth -1 = root library, 0..n = folder at that depth
    if (depth < 0) {
      setNavPath([]);
      setScreen("library");
      setSelectedDoc(null);
      setSelectedDocDetail(null);
      setCurrentFolder(null);
      await loadRootFolders();
    } else {
      const nextPath = navPath.slice(0, depth + 1);
      setNavPath(nextPath);
      setScreen("folder");
      setSelectedDoc(null);
      setSelectedDocDetail(null);
      setCurrentFolder(null);
      await loadFolder(nextPath[nextPath.length - 1].id);
    }
  }

  async function openDoc(document: ApiDocument) {
    setSelectedDoc(document);
    setSelectedDocDetail(null);
    setScreen("document");
    // Full text is only ever available from the detail endpoint -- the
    // folder listing's ApiDocument deliberately never carries original_text.
    try {
      setSelectedDocDetail(await fetchDocument(document.id));
    } catch {
      // leave selectedDocDetail null -- DocumentDetailScreen shows a loading state
    }
  }

  // Upload -> (extraction already ran server-side) -> analyse -> Terms Found,
  // for a document with usable extracted text. A document with no usable
  // text yet (image, scanned PDF, or extraction failure) has nothing to
  // analyse, so it lands in its folder exactly as before Phase 5.
  async function uploadAndAnalyse(folder: ApiFolder, name: string, file: File): Promise<void> {
    const uploaded = await uploadDocument(folder, name, file);
    if (uploaded.extraction_status !== "extracted") {
      await drillInto(folder);
      return;
    }
    const analysed = await analyseDocument(uploaded.id);
    // Establishes a coherent breadcrumb trail (Documents > folder > doc) for
    // the Back button on the Document Detail screen this flow eventually
    // reaches, the same shape drillInto() would have set.
    setNavPath([{ id: folder.id, name: folder.name }]);
    setSelectedDoc(uploaded);
    setSelectedDocDetail(analysed);
    setScreen("terms-found");
  }

  // Persists the user's term selection so it survives a refresh/reopen.
  // Best-effort: a transient failure here doesn't lose the local selection
  // the user sees -- their next toggle sends the current full state again.
  async function updateSelection(termSelection: Record<string, boolean>) {
    if (!selectedDoc) return;
    try {
      setSelectedDocDetail(await updateTermSelection(selectedDoc.id, termSelection));
    } catch {
      // best-effort -- see comment above
    }
  }

  // Runs the real ClearMed simplification pipeline and, on success, opens
  // Document Detail on the Plain Language tab's result. On failure this
  // throws -- TermsFoundScreen catches it, shows the error, and keeps the
  // user right there so they can retry without losing their selection.
  async function simplifyAndOpenDocument(): Promise<void> {
    if (!selectedDoc) return;
    const updated = await simplifyDocument(selectedDoc.id);
    setSelectedDocDetail(updated);
    setScreen("document");
  }

  // TermsFoundScreen brings its own full-screen header/back-button/bottom bar
  // (see the component), so -- like "login" -- it renders standalone, not
  // nested inside the shared AppBar/BottomNav shell.
  const isApp = screen !== "login" && screen !== "terms-found";

  return (
    <>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
      `}</style>
      <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#F9F7F5", overflow: "hidden" }}>
        {screen === "login" && <LoginScreen onLogin={login} />}

        {screen === "terms-found" && selectedDocDetail && (
          <TermsFoundScreen
            docName={selectedDoc?.name ?? "Document"}
            terms={selectedDocDetail.detected_terms ?? []}
            initialSelection={selectedDocDetail.term_selection ?? {}}
            onBack={() => setScreen("upload")}
            onSelectionChange={updateSelection}
            onSimplify={simplifyAndOpenDocument}
          />
        )}

        {isApp && (
          <>
            <AppBar
              screen={screen}
              navPath={navPath}
              docName={selectedDoc?.name ?? null}
              onNavigateTo={navigateTo}
            />

            <div style={{ flex: 1, overflowY: "auto" }}>
              {screen === "library" && (
                <LibraryScreen
                  docs={docs}
                  folders={rootFolders}
                  onOpenFolder={drillInto}
                  onCreateFolder={createRootFolder}
                />
              )}
              {screen === "folder" && currentFolder && (
                <FolderScreen
                  folder={currentFolder}
                  onOpenFolder={drillInto}
                  onOpenDoc={openDoc}
                  onCreateFolder={createChildFolder}
                />
              )}
              {screen === "upload" && (
                <UploadScreen folders={rootFolders} onUpload={uploadAndAnalyse} />
              )}
              {screen === "document" && selectedDoc && (
                <DocumentDetailScreen doc={selectedDoc} detail={selectedDocDetail} onRetrySimplify={simplifyAndOpenDocument} />
              )}
            </div>

            {screen !== "document" && screen !== "folder" && (
              <BottomNav
                active={screen as "upload" | "library"}
                onNavigate={s => {
                  setScreen(s);
                  setNavPath([]);
                  setSelectedDoc(null);
                  setSelectedDocDetail(null);
                  if (s === "library") loadRootFolders();
                }}
                onLogout={logout}
              />
            )}
          </>
        )}
      </div>
    </>
  );
}
