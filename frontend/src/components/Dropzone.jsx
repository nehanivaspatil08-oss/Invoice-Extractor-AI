import { useState } from "react";
import { UploadCloud } from "lucide-react";

/** Drag-and-drop or click-to-browse upload area. Accepts several files at once. */
export default function Dropzone({ onFiles, compact = false }) {
  const [over, setOver] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setOver(false);
    if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files);
  };

  return (
    <label
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={handleDrop}
      className={`group relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed text-center transition-colors focus-within:ring-2 focus-within:ring-brand focus-within:ring-offset-2 focus-within:ring-offset-page
        ${over ? "border-brand bg-brand-soft" : "border-line bg-surface hover:border-brand/60 hover:bg-brand-soft/40"}
        ${compact ? "gap-1 px-4 py-5" : "gap-3 px-6 py-14 sm:py-20"}`}
    >
      <input
        type="file"
        multiple
        accept=".pdf,.png,.jpg,.jpeg,.txt,application/pdf,image/png,image/jpeg"
        className="sr-only"
        onChange={(e) => { if (e.target.files.length) onFiles(e.target.files); e.target.value = ""; }}
      />
      <span className={`grid place-items-center rounded-full bg-brand-soft text-brand ${compact ? "h-9 w-9" : "h-14 w-14"}`}>
        <UploadCloud className={compact ? "h-5 w-5" : "h-7 w-7"} />
      </span>
      <span className={`font-bold ${compact ? "text-sm" : "text-lg"}`}>
        {compact ? "Add more invoices" : "Drop invoices here, or click to choose files"}
      </span>
      <span className="text-sm text-muted">PDF, JPG or PNG, up to 15 MB each. Scans and phone photos are read with OCR.</span>
    </label>
  );
}
