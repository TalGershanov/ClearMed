import { useState } from "react";
import { Field } from "@/components/Field";
import { Logo } from "@/components/Logo";
import { EyeIcon, EyeOffIcon } from "@/components/icons";
import { inputStyle } from "@/lib/ui";

export function SignupScreen({ onSignup, onNavigateToLogin }: {
  onSignup: (email: string, name: string, password: string) => Promise<void>;
  onNavigateToLogin: () => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    if (password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await onSignup(email, name, password);
      // success: the app switches away from this screen
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create your account. Please try again.");
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#F9F7F5" }}>
      {/* Logo at top */}
      <div style={{ paddingTop: "calc(env(safe-area-inset-top) + 48px)", paddingBottom: "40px", display: "flex", justifyContent: "center", flexShrink: 0 }}>
        <Logo height={110} />
      </div>

      {/* Form */}
      <div style={{ flex: 1, overflowY: "auto", padding: "0 24px calc(env(safe-area-inset-bottom) + 32px)", maxWidth: 420, width: "100%", alignSelf: "center" }}>

        <h2 style={{ fontFamily: "Outfit, sans-serif", fontSize: 26, fontWeight: 700, color: "#2C2420", marginBottom: 6 }}>Create your account</h2>
        <p style={{ color: "#9B9390", fontSize: 15, marginBottom: 32, fontFamily: "Outfit, sans-serif" }}>Sign up to start organizing your health records</p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <Field label="Full name">
            <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Jane Doe" required style={inputStyle} />
          </Field>
          <Field label="Email address">
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required style={inputStyle} />
          </Field>
          <Field label="Password">
            <div style={{ position: "relative" }}>
              <input type={showPw ? "text" : "password"} value={password} onChange={e => setPassword(e.target.value)} placeholder="At least 8 characters" required minLength={8} style={{ ...inputStyle, paddingRight: 46 }} />
              <button type="button" onClick={() => setShowPw(v => !v)} style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: "#9B9390", padding: 0, display: "flex" }}>
                {showPw ? <EyeOffIcon /> : <EyeIcon />}
              </button>
            </div>
          </Field>
          <Field label="Confirm password">
            <input type={showPw ? "text" : "password"} value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} placeholder="••••••••" required style={inputStyle} />
          </Field>
          {error && <p style={{ color: "#E07B55", fontSize: 13, fontFamily: "Outfit, sans-serif", marginTop: -8 }}>{error}</p>}
          <button type="submit" disabled={loading} style={{ marginTop: 4, padding: "16px", background: loading ? "#F0A888" : "#E07B55", color: "#fff", border: "none", borderRadius: 14, fontFamily: "Outfit, sans-serif", fontSize: 17, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer", transition: "background 0.2s" }}>
            {loading ? "Creating account…" : "Sign up"}
          </button>
        </form>

        <div style={{ marginTop: 28, textAlign: "center" }}>
          <span style={{ color: "#9B9390", fontSize: 14, fontFamily: "Outfit, sans-serif" }}>Already have an account? </span>
          <a href="#" onClick={e => { e.preventDefault(); onNavigateToLogin(); }} style={{ color: "#7BAAC8", fontSize: 14, fontWeight: 600, fontFamily: "Outfit, sans-serif", textDecoration: "none" }}>Log in</a>
        </div>

      </div>

    </div>
  );
}
