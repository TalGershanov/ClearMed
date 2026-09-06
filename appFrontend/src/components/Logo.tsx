import logoImg from "@/imports/image.png";

// mix-blend-mode: multiply makes the white logo background transparent on light surfaces
export function Logo({ height = 32 }: { height?: number }) {
  return (
    <img
      src={logoImg}
      alt="ClearMed"
      style={{ height, width: "auto", display: "block", mixBlendMode: "multiply", filter: "contrast(1.1)" }}
    />
  );
}
