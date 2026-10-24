"""Play against a trained network in the browser: game sessions, the AI service and the web server.

The server talks to the engine only through `engine` (new_game, legal_options, step) and
`state.clone`, so a faster engine with the same functions can replace it.
"""
