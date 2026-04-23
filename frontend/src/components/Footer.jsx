export default function Footer() {
  return (
    <footer className="mt-16 border-t border-ash-200 py-4">
      <div className="max-w-[1400px] mx-auto px-6 flex justify-between items-center text-[10.5px] text-ash-500">
        <div>Yield Intelligence · v0.1 · Demo build</div>
        <div className="flex items-center gap-4">
          <a className="hover:text-ink cursor-pointer">Data &amp; sources</a>
          <a className="hover:text-ink cursor-pointer">Model diagnostics</a>
          <a className="hover:text-ink cursor-pointer">Audit log</a>
        </div>
      </div>
    </footer>
  );
}
