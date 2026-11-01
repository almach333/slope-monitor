import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <div className="py-24 text-center">
      <div className="eyebrow">Error 404</div>
      <h1 className="mt-2 text-3xl font-bold text-white">Page not found</h1>
      <Link to="/" className="mt-4 inline-block text-accent hover:underline">
        ← Back to the dashboard
      </Link>
    </div>
  )
}
