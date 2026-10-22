export function CrashScreen() {
  return (
    <div role="alert" className="min-h-screen flex items-center justify-center p-6 text-center">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Something went wrong</h1>
        <p className="text-gray-700 mt-2">The dashboard hit an unexpected error. Reload to try again.</p>
        <button className="btn-primary mt-4" onClick={() => window.location.reload()}>Reload</button>
      </div>
    </div>
  )
}
