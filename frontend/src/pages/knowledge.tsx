import React, { useEffect, useRef, useState } from "react";
import type { NextPage } from "next";
import Layout from "@/components/Layout";
import PageHeader from "@/components/PageHeader";
import ErrorAlert from "@/components/ErrorAlert";
import ConfirmDialog from "@/components/ConfirmDialog";
import {
  api,
  errorMessage,
  type KnowledgeDocument,
  type KnowledgeTicket,
} from "@/lib/api";
import { SYSTEMS } from "@/lib/constants";

type PendingDelete = { kind: "ticket" | "document"; id: string; title: string };

const Page: NextPage = () => {
  const [tickets, setTickets] = useState<KnowledgeTicket[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [stats, setStats] = useState({ tickets: 0, documents: 0, document_chunks: 0 });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [deleting, setDeleting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [ticketForm, setTicketForm] = useState({
    ticket_id: "",
    title: "",
    description: "",
    resolution: "",
    system: "SAP",
    category: "basis",
    sap_notes: "",
    transactions: "",
    error_codes: "",
  });

  const [docForm, setDocForm] = useState({
    document_id: "",
    title: "",
    source_type: "sap_note",
    system: "SAP",
    category: "basis",
    text: "",
  });

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsResult, ticketResult, documentResult] = await Promise.all([
        api.getKnowledgeStats(),
        api.listKnowledgeTickets(),
        api.listKnowledgeDocuments(),
      ]);
      setStats(statsResult);
      setTickets(ticketResult);
      setDocuments(documentResult);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  /** Run a library mutation, then show its notice and refresh the lists. */
  const runAction = async <T,>(action: () => Promise<T>, describe: (result: T) => string) => {
    setError(null);
    try {
      const result = await action();
      setNotice(describe(result));
      await load();
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    }
  };

  const submitTicket = (event: React.FormEvent) => {
    event.preventDefault();
    runAction(
      () => api.ingestTicket({ ...ticketForm, status: "resolved", resolver: "consultant" }),
      (result) =>
        `Ingested ${result.ticket_id} (${result.chunk_count ?? 0} chunks). Resolution stays attached to every chunk.`
    );
  };

  const submitDocument = (event: React.FormEvent) => {
    event.preventDefault();
    runAction(
      () => api.ingestDocument(docForm),
      (result) => `Ingested ${result.document_id} (${result.chunk_count ?? 0} heading/token chunks).`
    );
  };

  const clearPendingFile = () => {
    setPendingFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const selectFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setPendingFile(file);
    setError(null);
  };

  const uploadSelectedFile = async () => {
    if (!pendingFile) return;
    const form = new FormData();
    form.append("file", pendingFile);
    form.append("title", pendingFile.name);
    form.append(
      "source_type",
      pendingFile.name.toLowerCase().endsWith(".pdf") ? "pdf" : "document"
    );
    form.append("system", docForm.system);
    form.append("category", docForm.category);
    if (docForm.document_id.trim()) {
      form.append("document_id", docForm.document_id.trim());
    }
    setUploading(true);
    const uploaded = await runAction(
      () => api.uploadDocument(form),
      (result) => `Uploaded ${result.document_id} (${result.chunk_count ?? 0} chunks).`
    );
    setUploading(false);
    if (uploaded) clearPendingFile();
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    const { kind, id } = pendingDelete;
    setDeleting(true);
    await runAction<unknown>(
      () => (kind === "ticket" ? api.deleteTicket(id) : api.deleteDocument(id)),
      () => `Deleted ${id} from the library.`
    );
    setDeleting(false);
    setPendingDelete(null);
  };

  const reingest = (id: string, action: (id: string) => Promise<unknown>) =>
    runAction(
      () => action(id),
      () => `Re-embedded ${id}`
    );

  return (
    <Layout fullWidth>
      <PageHeader
        title="Knowledge Library"
        subtitle="Ingest resolved tickets, SAP Notes, and PDFs. SOLVIA chunks by headings, keeps the resolution with the symptom, and re-embeds on update."
      />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Tickets" value={stats.tickets} />
        <StatCard label="Documents" value={stats.documents} />
        <StatCard label="Document chunks" value={stats.document_chunks} />
      </div>

      {error && <ErrorAlert message={error} onRetry={load} />}
      {notice && (
        <p className="mb-5 rounded-xl border border-emerald-400/25 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-200">
          {notice}
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <form
          onSubmit={submitTicket}
          className="rounded-2xl border border-white/[0.1] bg-gradient-to-br from-[#111a2d] to-[#0b1424] p-6"
        >
          <h2 className="text-lg font-semibold text-white">Resolved ticket</h2>
          <p className="mt-1 mb-5 text-sm text-slate-400">
            Symptom and resolution are stored together so search never returns a problem without its fix.
          </p>
          <Field
            label="Ticket ID"
            value={ticketForm.ticket_id}
            onChange={(value) => setTicketForm({ ...ticketForm, ticket_id: value })}
            placeholder="T-20441"
            required
          />
          <Field
            label="Title"
            value={ticketForm.title}
            onChange={(value) => setTicketForm({ ...ticketForm, title: value })}
            required
          />
          <TextArea
            label="Description / symptom"
            value={ticketForm.description}
            onChange={(value) => setTicketForm({ ...ticketForm, description: value })}
            required
          />
          <TextArea
            label="Resolution"
            value={ticketForm.resolution}
            onChange={(value) => setTicketForm({ ...ticketForm, resolution: value })}
          />
          <div className="grid grid-cols-2 gap-3">
            <Select
              label="System"
              value={ticketForm.system}
              onChange={(value) => setTicketForm({ ...ticketForm, system: value })}
              options={SYSTEMS}
            />
            <Field
              label="Category"
              value={ticketForm.category}
              onChange={(value) => setTicketForm({ ...ticketForm, category: value })}
            />
          </div>
          <Field
            label="SAP Notes"
            value={ticketForm.sap_notes}
            onChange={(value) => setTicketForm({ ...ticketForm, sap_notes: value })}
            placeholder="1234567"
          />
          <Field
            label="Transactions"
            value={ticketForm.transactions}
            onChange={(value) => setTicketForm({ ...ticketForm, transactions: value })}
            placeholder="ST22, SU53"
          />
          <Field
            label="Error codes"
            value={ticketForm.error_codes}
            onChange={(value) => setTicketForm({ ...ticketForm, error_codes: value })}
            placeholder="TIME_OUT, ORA-00060"
          />
          <button
            type="submit"
            className="mt-4 w-full rounded-xl bg-gradient-to-r from-violet-600 via-indigo-500 to-cyan-400 px-5 py-3 text-sm font-semibold text-white"
          >
            Ingest ticket
          </button>
        </form>

        <form
          onSubmit={submitDocument}
          className="rounded-2xl border border-white/[0.1] bg-gradient-to-br from-[#111a2d] to-[#0b1424] p-6"
        >
          <h2 className="text-lg font-semibold text-white">SAP Note / document</h2>
          <p className="mt-1 mb-5 text-sm text-slate-400">
            Paste text or upload a PDF. Chunking follows headings, then packs ~400 tokens with overlap.
          </p>
          <Field
            label="Document ID"
            value={docForm.document_id}
            onChange={(value) => setDocForm({ ...docForm, document_id: value })}
            placeholder="DOC-SNOTE-001"
            required
          />
          <Field
            label="Title"
            value={docForm.title}
            onChange={(value) => setDocForm({ ...docForm, title: value })}
            required
          />
          <div className="grid grid-cols-2 gap-3">
            <Select
              label="Source type"
              value={docForm.source_type}
              onChange={(value) => setDocForm({ ...docForm, source_type: value })}
              options={["sap_note", "pdf", "manual", "markdown"]}
            />
            <Select
              label="System"
              value={docForm.system}
              onChange={(value) => setDocForm({ ...docForm, system: value })}
              options={SYSTEMS}
            />
          </div>
          <TextArea
            label="Text"
            value={docForm.text}
            onChange={(value) => setDocForm({ ...docForm, text: value })}
            required
          />
          <div className="mb-3 mt-2 text-sm text-slate-300">
            <p>Upload PDF / text</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt,.md"
              onChange={selectFile}
              aria-label="Upload PDF / text"
              className="mt-2 block w-full text-sm text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-500/20 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-indigo-200"
            />
          </div>
          {pendingFile && (
            <div className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-indigo-400/25 bg-indigo-500/10 px-3 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-white">{pendingFile.name}</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {(pendingFile.size / 1024).toFixed(1)} KB · not uploaded yet
                </p>
              </div>
              <button
                type="button"
                onClick={clearPendingFile}
                className="shrink-0 rounded-lg border border-rose-400/30 bg-rose-400/10 px-3 py-1.5 text-xs font-semibold text-rose-200"
              >
                Remove file
              </button>
            </div>
          )}
          <button
            type="button"
            onClick={uploadSelectedFile}
            disabled={!pendingFile || uploading}
            className="mb-3 w-full rounded-xl bg-indigo-500/20 px-5 py-3 text-sm font-semibold text-indigo-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {uploading ? "Uploading..." : "Upload selected file"}
          </button>
          <button
            type="submit"
            className="mt-2 w-full rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-5 py-3 text-sm font-semibold text-cyan-100"
          >
            Ingest pasted document
          </button>
        </form>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <LibraryList
          title="Tickets in library"
          empty="No tickets yet. Ingest a resolved incident above."
          items={tickets.map((ticket) => ({
            id: ticket.ticket_id,
            title: ticket.title,
            meta: `${ticket.system || "n/a"} · ${ticket.category || "n/a"} · score ${(
              ticket.feedback_score ?? 0.5
            ).toFixed(2)}`,
            onReingest: () => reingest(ticket.ticket_id, api.reingestTicket),
            onDelete: () =>
              setPendingDelete({ kind: "ticket", id: ticket.ticket_id, title: ticket.title }),
          }))}
        />
        <LibraryList
          title="Documents in library"
          empty="No documents yet. Paste a SAP Note or upload a PDF."
          items={documents.map((document) => ({
            id: document.document_id,
            title: document.title,
            meta: `${document.source_type} · ${document.chunk_count ?? 0} chunks`,
            onReingest: () => reingest(document.document_id, api.reingestDocument),
            onDelete: () =>
              setPendingDelete({ kind: "document", id: document.document_id, title: document.title }),
          }))}
        />
      </div>
      {loading && <p className="mt-4 text-sm text-slate-500">Refreshing library...</p>}

      <ConfirmDialog
        open={pendingDelete !== null}
        title={`Delete this ${pendingDelete?.kind ?? "item"}?`}
        message={
          <>
            <span className="font-medium text-white">
              {pendingDelete?.title} ({pendingDelete?.id})
            </span>{" "}
            will be removed from the knowledge library, and its search chunks are deleted. This
            cannot be undone.
          </>
        }
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </Layout>
  );
};

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-[#0b1424] px-5 py-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <label className="mb-3 block text-sm text-slate-300">
      <FieldLabel label={label} required={required} />
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        className="mt-1 w-full rounded-xl border border-white/10 bg-[#030817] px-3 py-2 text-sm text-white outline-none focus:border-indigo-400"
      />
    </label>
  );
}

function FieldLabel({ label, required }: { label: string; required: boolean }) {
  return (
    <>
      {label}
      {required && <span className="ml-0.5 text-rose-400">*</span>}
    </>
  );
}

function TextArea({
  label,
  value,
  onChange,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <label className="mb-3 block text-sm text-slate-300">
      <FieldLabel label={label} required={required} />
      <textarea
        rows={4}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
        className="mt-1 w-full rounded-xl border border-white/10 bg-[#030817] px-3 py-2 text-sm text-white outline-none focus:border-indigo-400"
      />
    </label>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  return (
    <label className="mb-3 block text-sm text-slate-300">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-xl border border-white/10 bg-[#030817] px-3 py-2 text-sm text-white outline-none focus:border-indigo-400"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function LibraryList({
  title,
  empty,
  items,
}: {
  title: string;
  empty: string;
  items: Array<{
    id: string;
    title: string;
    meta: string;
    onReingest: () => void;
    onDelete: () => void;
  }>;
}) {
  return (
    <section className="rounded-2xl border border-white/[0.08] bg-[#0b1424] p-5">
      <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-slate-400">{title}</h3>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">{empty}</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {items.map((item) => (
            <li
              key={item.id}
              className="flex items-start justify-between gap-3 rounded-xl border border-white/[0.06] px-3 py-3"
            >
              <div>
                <p className="text-sm font-medium text-white">{item.title}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {item.id} · {item.meta}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  onClick={item.onReingest}
                  className="text-xs font-semibold text-cyan-300"
                >
                  Re-embed
                </button>
                <button
                  type="button"
                  onClick={item.onDelete}
                  className="text-xs font-semibold text-rose-300"
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default Page;
