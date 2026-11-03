# How we build boards here

Short, current guidance for starting and finishing a board in this
repository. Read these before a new board; they are kept small on purpose.

| File | What it covers |
|---|---|
| [new-board.md](new-board.md) | The workflow from idea to merged board, and what "done" means |
| [versioning.md](versioning.md) | Products and revisions: changed in place, numbered in the code and on the board, frozen by a git tag when ordered; tests belong to a revision and are questioned before each new one |
| [repo-structure.md](repo-structure.md) | Folder layout (`products/`), what to commit, keeping the repository small, how CI runs |
| [brand.md](brand.md) | How a board carries the OffGrid brand |
| [lessons.md](lessons.md) | What we learned building boards: physics, fabs and tools |
| [product-video.md](product-video.md) | A board's product video: the exploded view rendered from its KiCad file, the house style, and the recipe for a new board |

Board-specific facts (part choices, stock checks, test results) live in the
product's own folder in `products/`, dated, not here. These pages hold only what applies to
every board and stays true.

Updating these pages is part of finishing a board: if a board taught us
something that will matter on the next one, add it to `lessons.md`; if a step
in `new-board.md` turned out wrong, fix it.
