# Ark Nova board

Play against a trained network (or a built-in bot) in the browser.

```bash
python -m arknova.play.server --checkpoint <path to a trained .pt>   # game server on :8765 (repo root)
python -m arknova.play.server --checkpoint greedy                     # or a built-in bot (beam_2x3, beam_3x8)
cd web && pnpm install && pnpm dev                                    # board on http://localhost:5173
```

`ARKNOVA_API=http://127.0.0.1:<port> pnpm dev` points the board at a game server on another port (for
example one reached through an SSH tunnel). `--remote <url>` makes the server use another server's network
for its moves (`/api/ai/analyse`); that server must let this one in without a login (`skip_login` in its
config.json). The server and its API are described in
`arknova/play/server.py`; settings such as login, accounts and guest play live in `arknova/play/config.py`.

Stack: React 19, TypeScript, Vite, Tailwind CSS 4, shadcn/ui.
