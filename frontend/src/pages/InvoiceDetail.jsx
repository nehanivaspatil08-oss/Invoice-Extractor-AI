import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import ReviewPanel from "../components/ReviewPanel.jsx";
import { ErrorBox, Spinner } from "../components/ui.jsx";

/** Opens one saved invoice from History in the same review screen used after upload. */
export default function InvoiceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setInvoice(null);
    api.get(id).then(setInvoice).catch((e) => setError(e.message));
  }, [id]);

  return (
    <>
      <Link to="/history" className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" />Back to history</Link>
      {error && <ErrorBox>{error}</ErrorBox>}
      {!invoice && !error && <div className="grid place-items-center py-20"><Spinner className="h-7 w-7 text-brand" /></div>}
      {invoice && <ReviewPanel invoice={invoice} onSaved={setInvoice} onDeleted={() => navigate("/history")} />}
    </>
  );
}
