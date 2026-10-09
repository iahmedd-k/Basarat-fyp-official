# Basarat public information site

A standalone React and TypeScript site for Basarat's Google OAuth verification and public
project information. It contains the project overview, privacy policy, and terms of service.
It is an informational site, not the full Basarat product interface.

## Local development

```sh
npm install
npm run dev
```

## Production build

```sh
npm run build
npm run preview
```

The production host must serve `index.html` as the fallback for client-side routes so direct
visits to `/privacy` and `/terms` load the React application.

## Routes

- `/` — project overview, main capabilities, and a link to the live Basarat API.
- `/privacy` — Google sign-in data, purposes, safeguards, retention, and user choices.
- `/terms` — service, account, and informational-content terms.
