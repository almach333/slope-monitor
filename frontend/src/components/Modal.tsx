/** A simple dialog built on the native <dialog> element (handles Esc and focus). */

import { type ReactNode, useEffect, useRef } from 'react'

import { CloseIcon } from './Icons'

export function Modal({
  open,
  onClose,
  title,
  children,
  wide = false,
}: {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  wide?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className={`m-auto max-h-[90vh] w-[calc(100%-2rem)] rounded-xl border border-line bg-panel p-0 text-slate-100 shadow-2xl backdrop:bg-black/70 ${
        wide ? 'max-w-6xl' : 'max-w-lg'
      }`}
    >
      {open && (
        <div className="flex max-h-[90vh] flex-col">
          <header className="flex items-center justify-between border-b border-line px-5 py-3">
            <h2 className="text-base font-semibold text-white">{title}</h2>
            <button type="button" onClick={onClose} aria-label="Close" className="text-muted hover:text-white">
              <CloseIcon />
            </button>
          </header>
          <div className="overflow-y-auto p-5">{children}</div>
        </div>
      )}
    </dialog>
  )
}
