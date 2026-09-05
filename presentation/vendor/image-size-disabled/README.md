# Disabled image parser

SPDX-License-Identifier: Apache-2.0

This Traigent-authored package stands in for `image-size`, which `pptxgenjs`
lists as a dependency but never loads: the only image-sizing helper in its
shipped build is commented out. Substituting it removes an unused image parser
from the install graph while keeping the lockfile registry-only, and if build
tooling ever does load the module, it throws immediately instead of parsing
image bytes. The presentation renders native text and shapes and supports no
images; `tests/build-pptx.test.ts` enforces that (no media entry, no picture
element), not this package.

The package contains no parser, file reader, network client, or dependency. It
must remain a development-only build guard and must never be emitted into the
customer bundle.
