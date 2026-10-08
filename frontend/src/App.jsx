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

  useEffect(() => {
    if (!file) return

    const url = URL.createObjectURL(file)
    setPreviewUrl(url)

    return () => URL.revokeObjectURL(url)
  }, [file])

  function selectFile(event) {
    const selected = event.target.files?.[0] || null

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
          disabled={busy}
        />
        <button disabled={!file || busy} type="submit">
          {busy ? 'Extracting…' : 'Extract invoice'}
        </button>
        <p>Up to 10 MiB and 25 pages. Scanned pages may take longer.</p>
      </form>

      {error && <p className="error" role="alert">{error}</p>}
      {busy && <p role="status">Processing your document…</p>}

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
          {!result ? (
            <p className="empty">Extract an invoice to begin your review.</p>
          ) : (
            <>
              <p className="summary">
                {result.page_count} page(s) ·{' '}
                {[...new Set(
                  result.pages.map((page) => page.extraction_method),
                )].join(', ')}
              </p>

              {result.status === 'no_text_found' && (
                <p className="error">No readable text was found.</p>
              )}

              <div className="fields">
                {fields.map(([key, label]) => (
                  <label key={key}>
                    {label}
                    <input
                      type={key.endsWith('_date') ? 'date' : 'text'}
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
                  Review required. Edits are held in this page only;
                  saving and approval will be added next.
                </p>
              </div>

              <details>
                <summary>Show extracted text</summary>
                <pre>
                  {result.pages.map((page) =>
                    `Page ${page.page_number}\n${page.text}`,
                  ).join('\n\n')}
                </pre>
              </details>
            </>
          )}
        </section>
      </div>
    </main>
  )
}
