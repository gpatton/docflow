import { useEffect, useState } from 'react'
import './App.css'

const fields = [
  ['supplier', 'Supplier'],
  ['invoice_number', 'Invoice number'],
  ['invoice_date', 'Invoice date'],
  ['due_date', 'Due date'],
  ['currency', 'Currency'],
  ['subtotal', 'Subtotal'],
  ['vat', 'VAT'],
  ['total', 'Total'],
]

function toCents(value) {
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(value.trim())
  if (!match) return null

  const cents =
    Number(match[1]) * 100 + Number((match[2] || '').padEnd(2, '0'))

  return Number.isSafeInteger(cents) ? cents : null
}

export default function App() {
  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [result, setResult] = useState(null)
  const [draft, setDraft] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [savedInvoices, setSavedInvoices] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [filename, setFilename] = useState('')
  const [invoiceStatus, setInvoiceStatus] = useState('draft')
  const [saving, setSaving] = useState(false)
  const [loadingInvoices, setLoadingInvoices] = useState(true)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadInvoices() {
      try {
        const response = await fetch('/api/invoices')
        if (!response.ok) throw new Error('Could not load saved invoices.')
        const data = await response.json()
        if (!cancelled) setSavedInvoices(data)
      } catch (failure) {
        if (!cancelled) setError(failure.message)
      } finally {
        if (!cancelled) setLoadingInvoices(false)
      }
    }

    loadInvoices()
    return () => { cancelled = true }
  }, [])

  async function saveDraft() {
    if (busy || saving || invoiceStatus !== 'draft') return

    setSaving(true)
    setError('')
    setNotice('')

    try {
      const response = await fetch(
        activeId ? `/api/invoices/${activeId}` : '/api/invoices',
        {
          method: activeId ? 'PUT' : 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            filename,
            fields: Object.fromEntries(
              fields.map(([key]) => [key, draft[key] || null]),
            ),
          }),
        },
      )
      const data = await response.json()
      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'The draft could not be saved. Check the field lengths.',
        )
      }

      setActiveId(data.id)
      setInvoiceStatus(data.status)
      setSavedInvoices((previous) => [
        data,
        ...previous.filter((invoice) => invoice.id !== data.id),
      ])
      setNotice('Draft saved.')
    } catch (failure) {
      setError(failure.message || 'Could not save the draft.')
    } finally {
      setSaving(false)
    }
  }

  async function openInvoice(id) {
    if (busy || saving) return
    if ((result || activeId) && !window.confirm(
      'Open this saved invoice? Any unsaved edits in the current review will be lost.',
    )) return

    setSaving(true)
    setError('')
    setNotice('')

    try {
      const response = await fetch(`/api/invoices/${id}`)
      const data = await response.json()
      if (!response.ok) throw new Error('Could not open the saved invoice.')

      setFile(null)
      setPreviewUrl('')
      setResult(null)
      setActiveId(data.id)
      setFilename(data.filename)
      setInvoiceStatus(data.status)
      setDraft(Object.fromEntries(
        fields.map(([key]) => [key, data.fields[key] ?? '']),
      ))
      setNotice('Saved invoice opened.')
    } catch (failure) {
      setError(failure.message || 'Could not open the invoice.')
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    if (!file) return

    const url = URL.createObjectURL(file)
    setPreviewUrl(url)

    return () => URL.revokeObjectURL(url)
  }, [file])

  function selectFile(event) {
    const selected = event.target.files?.[0] || null

    setActiveId(null)
    setFilename(selected?.name || '')
    setInvoiceStatus('draft')
    setNotice('')
    setFile(selected)
    setPreviewUrl('')
    setResult(null)
    setDraft({})
    setError('')
  }

  async function extract(event) {
    event.preventDefault()
    if (!file || busy) return

    if (file.size > 10 * 1024 * 1024) {
      setError('Choose a PDF smaller than or equal to 10 MiB.')
      return
    }

    setActiveId(null)
    setInvoiceStatus('draft')
    setNotice('')
    setBusy(true)
    setError('')
    setResult(null)
    setDraft({})

    try {
      const body = new FormData()
      body.append('file', file)

      const response = await fetch('/api/documents/extract', {
        method: 'POST',
        body,
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'The document could not be processed.',
        )
      }

      setResult(data)
      setDraft(
        Object.fromEntries(
          fields.map(([key]) => [key, data.invoice?.fields?.[key] ?? '']),
        ),
      )
    } catch (failure) {
      setError(failure.message || 'Could not connect to DocFlow.')
    } finally {
      setBusy(false)
    }
  }

  const missing = fields
    .filter(([key]) => !draft[key]?.trim())
    .map(([, label]) => label)

  const amounts = ['subtotal', 'vat', 'total'].map((key) =>
    toCents(draft[key] || ''),
  )
  const validAmounts = amounts.every((amount) => amount !== null)
  const totalsMatch =
    validAmounts && amounts[0] + amounts[1] === amounts[2]

  return (
    <main className="app">
      <header>
        <p className="eyebrow">DOCUMENT REVIEW</p>
        <h1>DocFlow</h1>
        <p>Upload an invoice, check the extraction, and correct its fields.</p>
      </header>

      <form className="upload" onSubmit={extract}>
        <label htmlFor="invoice-file">Invoice PDF</label>
        <input
          id="invoice-file"
          type="file"
          accept=".pdf,application/pdf"
          onChange={selectFile}
          disabled={busy || saving}
        />
        <button disabled={!file || busy || saving} type="submit">
          {busy ? 'Extracting…' : 'Extract invoice'}
        </button>
        <p>Up to 10 MiB and 25 pages. Scanned pages may take longer.</p>
      </form>

      {error && <p className="error" role="alert">{error}</p>}
      {busy && <p role="status">Processing your document…</p>}
      {notice && <p role="status">{notice}</p>}

      <section className="panel">
        <h2>Saved invoices</h2>
        {loadingInvoices ? (
          <p>Loading saved invoices…</p>
        ) : savedInvoices.length === 0 ? (
          <p>No saved invoices yet.</p>
        ) : (
          <ul>
            {savedInvoices.map((invoice) => (
              <li key={invoice.id}>
                <button
                  type="button"
                  disabled={busy || saving}
                  onClick={() => openInvoice(invoice.id)}
                >
                  {invoice.fields.invoice_number || invoice.filename}
                  {' · '}{invoice.status}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="workspace">
        <section className="panel">
          <h2>Original invoice</h2>
          {previewUrl ? (
            <>
              <p className="filename">{file.name}</p>
              <iframe title="Original invoice PDF" src={previewUrl} />
              <a href={previewUrl} target="_blank" rel="noreferrer">
                Open PDF in a separate tab
              </a>
            </>
          ) : (
            <p className="empty">Choose a PDF to preview it here.</p>
          )}
        </section>

        <section className="panel">
          <h2>Review extracted fields</h2>
          {!result && !activeId ? (
            <p className="empty">Extract an invoice to begin your review.</p>
          ) : (
            <>
              <p className="filename">{filename}</p>
              <p>Status: {invoiceStatus}</p>
              {result && <p className="summary">
                {result.page_count} page(s) ·{' '}
                {[...new Set(
                  result.pages.map((page) => page.extraction_method),
                )].join(', ')}
              </p>}

              {result?.status === 'no_text_found' && (
                <p className="error">No readable text was found.</p>
              )}

              <div className="fields">
                {fields.map(([key, label]) => (
                  <label key={key}>
                    {label}
                    <input
                      type={key.endsWith('_date') ? 'date' : 'text'}
                      disabled={busy || saving || invoiceStatus !== 'draft'}
                      value={draft[key] || ''}
                      onChange={(event) => setDraft({
                        ...draft,
                        [key]: event.target.value,
                      })}
                    />
                  </label>
                ))}
              </div>

              <div className="checks" aria-live="polite">
                <h3>Current draft checks</h3>
                <p>
                  {missing.length
                    ? `Missing: ${missing.join(', ')}`
                    : 'All fields are filled.'}
                </p>
                <p>
                  {!validAmounts
                    ? 'Enter valid amounts with up to two decimal places.'
                    : totalsMatch
                      ? 'Subtotal + VAT matches the total.'
                      : 'Subtotal + VAT does not match the total.'}
                </p>
                <p className="muted">
                  Review required. Save your changes before leaving this
                  page. Approval will be added next.
                </p>
              </div>

              <button
                type="button"
                disabled={busy || saving || invoiceStatus !== 'draft'}
                onClick={saveDraft}
              >
                {saving ? 'Working…' : 'Save draft'}
              </button>

              {result && <details>
                <summary>Show extracted text</summary>
                <pre>
                  {result.pages.map((page) =>
                    `Page ${page.page_number}\n${page.text}`,
                  ).join('\n\n')}
                </pre>
              </details>}
            </>
          )}
        </section>
      </div>
    </main>
  )
}
