# vinted-notifier

Controlla le ricerche Vinted elencate in `config.json` ogni 30 minuti circa (GitHub Actions) e invia su Telegram ogni articolo nuovo.

- Ricerche: modifica `config.json` e aggiungi `{ "name": "...", "url": "URL della ricerca Vinted" }` dentro `searches`.
- Token del bot: Secret `TELEGRAM_BOT_TOKEN` (Settings → Secrets and variables → Actions).
- Avvio manuale: scheda Actions → Vinted Notifier → Run workflow.
