// ─── Icons ────────────────────────────────────────────────────────────────────
export function FolderPlusIcon() {
  return <svg width={15} height={15} viewBox="0 0 24 24" fill="none"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V7a2 2 0 012-2h5l2 2h9a2 2 0 012 2z" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" /><line x1="12" y1="11" x2="12" y2="17" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" /><line x1="9" y1="14" x2="15" y2="14" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" /></svg>;
}
export function ImageIcon() {
  return <svg width={16} height={16} viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth={1.8} /><circle cx="8.5" cy="8.5" r="1.5" fill="currentColor" /><polyline points="21 15 16 10 5 21" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
export function LogoutIcon() {
  return <svg width={20} height={20} viewBox="0 0 24 24" fill="none"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" /><polyline points="16 17 21 12 16 7" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" /><line x1="21" y1="12" x2="9" y2="12" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" /></svg>;
}
export function FolderNavIcon({ active }: { active: boolean }) {
  return <svg width={22} height={22} viewBox="0 0 24 24" fill="none"><path d="M2 8a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V8z" fill={active ? "#E07B55" : "none"} stroke={active ? "#E07B55" : "#9B9390"} strokeWidth={1.8} /></svg>;
}
export function UploadNavIcon({ active }: { active: boolean }) {
  const c = active ? "#E07B55" : "#9B9390";
  return <svg width={22} height={22} viewBox="0 0 24 24" fill="none"><path d="M12 16V8m0 0l-3 3m3-3l3 3" stroke={c} strokeWidth={1.8} strokeLinecap="round" /><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1" stroke={c} strokeWidth={1.8} strokeLinecap="round" /></svg>;
}
export function FolderFillIcon({ color }: { color: string }) {
  return <svg width={22} height={22} viewBox="0 0 24 24" fill="none"><path d="M2 8a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V8z" fill={color} /></svg>;
}
export function ChevronIcon() {
  return <svg width={15} height={15} viewBox="0 0 24 24" fill="none"><path d="M9 18l6-6-6-6" stroke="#C4BDB9" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
export function BackIcon() {
  return <svg width={20} height={20} viewBox="0 0 24 24" fill="none"><path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
export function PlusIcon() {
  return <svg width={14} height={14} viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" /></svg>;
}
export function SearchIcon() {
  return <svg width={15} height={15} viewBox="0 0 24 24" fill="none"><circle cx={11} cy={11} r={8} stroke="currentColor" strokeWidth={2} /><path d="M21 21l-4.35-4.35" stroke="currentColor" strokeWidth={2} strokeLinecap="round" /></svg>;
}
export function EyeIcon() {
  return <svg width={17} height={17} viewBox="0 0 24 24" fill="none"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" stroke="currentColor" strokeWidth={1.8} /><circle cx={12} cy={12} r={3} stroke="currentColor" strokeWidth={1.8} /></svg>;
}
export function EyeOffIcon() {
  return <svg width={17} height={17} viewBox="0 0 24 24" fill="none"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24M1 1l22 22" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" /></svg>;
}
export function UploadCloudIcon() {
  return <svg width={26} height={26} viewBox="0 0 24 24" fill="none"><polyline points="16 16 12 12 8 16" stroke="#E07B55" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" /><line x1="12" y1="12" x2="12" y2="21" stroke="#E07B55" strokeWidth={1.8} strokeLinecap="round" /><path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3" stroke="#E07B55" strokeWidth={1.8} strokeLinecap="round" /></svg>;
}
export function CameraIcon() {
  return <svg width={22} height={22} viewBox="0 0 24 24" fill="none"><path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" /><circle cx={12} cy={13} r={4} stroke="currentColor" strokeWidth={1.8} /></svg>;
}
export function ScanIcon() {
  return <svg width={22} height={22} viewBox="0 0 24 24" fill="none"><path d="M3 7V5a2 2 0 012-2h2M17 3h2a2 2 0 012 2v2M21 17v2a2 2 0 01-2 2h-2M7 21H5a2 2 0 01-2-2v-2" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" /><line x1="3" y1="12" x2="21" y2="12" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" /></svg>;
}
export function PDFIcon({ color }: { color: string }) {
  return <svg width={20} height={20} viewBox="0 0 24 24" fill="none"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" stroke={color} strokeWidth={1.8} /><polyline points="14 2 14 8 20 8" stroke={color} strokeWidth={1.8} /></svg>;
}
export function ScanDocIcon({ color }: { color: string }) {
  return <svg width={20} height={20} viewBox="0 0 24 24" fill="none"><rect x="4" y="2" width="16" height="20" rx="2" stroke={color} strokeWidth={1.8} /><line x1="8" y1="8" x2="16" y2="8" stroke={color} strokeWidth={1.5} strokeLinecap="round" /><line x1="8" y1="12" x2="16" y2="12" stroke={color} strokeWidth={1.5} strokeLinecap="round" /><line x1="8" y1="16" x2="13" y2="16" stroke={color} strokeWidth={1.5} strokeLinecap="round" /></svg>;
}
export function SparkIcon() {
  return <svg width={15} height={15} viewBox="0 0 24 24" fill="none"><path d="M12 2l2.4 7.6H22l-6.4 4.6 2.4 7.6L12 17.2 5.9 21.8l2.5-7.6L2 9.6h7.6z" stroke="#E07B55" strokeWidth={1.8} fill="none" strokeLinejoin="round" /></svg>;
}
export function NoteIcon() {
  return <svg width={15} height={15} viewBox="0 0 24 24" fill="none"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" stroke="#7BAAC8" strokeWidth={1.8} /><line x1="16" y1="13" x2="8" y2="13" stroke="#7BAAC8" strokeWidth={1.5} strokeLinecap="round" /><line x1="16" y1="17" x2="8" y2="17" stroke="#7BAAC8" strokeWidth={1.5} strokeLinecap="round" /></svg>;
}
export function ShareIcon() {
  return <svg width={15} height={15} viewBox="0 0 24 24" fill="none"><circle cx={18} cy={5} r={3} stroke="#7BAAC8" strokeWidth={1.8} /><circle cx={6} cy={12} r={3} stroke="#7BAAC8" strokeWidth={1.8} /><circle cx={18} cy={19} r={3} stroke="#7BAAC8" strokeWidth={1.8} /><line x1="8.59" y1="13.51" x2="15.42" y2="17.49" stroke="#7BAAC8" strokeWidth={1.8} strokeLinecap="round" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" stroke="#7BAAC8" strokeWidth={1.8} strokeLinecap="round" /></svg>;
}
export function Spinner() {
  return <div style={{ width: 34, height: 34, border: "3px solid #EDE9E5", borderTopColor: "#E07B55", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />;
}
export function CheckCircle() {
  return <div style={{ width: 48, height: 48, borderRadius: "50%", background: "rgba(123,170,200,0.12)", display: "flex", alignItems: "center", justifyContent: "center" }}><svg width={24} height={24} viewBox="0 0 24 24" fill="none"><path d="M20 6L9 17l-5-5" stroke="#7BAAC8" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" /></svg></div>;
}
