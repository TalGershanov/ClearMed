export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      <label style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, fontWeight: 600, color: "#6B6460" }}>{label}</label>
      {children}
    </div>
  );
}
