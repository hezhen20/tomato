# Third-party notices

## Material and appearance references

- [Microsoft WinUI Gallery](https://github.com/microsoft/WinUI-Gallery) and [Acrylic material guidance](https://learn.microsoft.com/windows/apps/design/style/acrylic): references for in-app blur, tint, texture and lighting layers.
- [Qt QGraphicsBlurEffect](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QGraphicsBlurEffect.html): the existing PySide6 dependency renders and caches the background blur. Text and controls are not blurred.
- [Catppuccin palette](https://github.com/catppuccin/palette): Latte/Mocha references for complementary light and dark roles. Dracula Alucard and adapted Nord hues provide readable light-mode accents.

The material implementation uses Qt's existing rendering APIs and a generated, deterministic texture. It requires no network access, external images or additional widget libraries.


## Accent palette references

Theme accents in `app/ui/theme.py` reference individual swatches from these mature open-source palettes:

- [Catppuccin palette](https://github.com/catppuccin/palette/blob/main/palette.json): Mocha Blue, Peach, Pink and Green. Copyright Catppuccin contributors; MIT license.
- [Dracula](https://github.com/dracula/dracula-theme#color-palette-oss): Purple. Copyright Zeno Rocha and contributors; MIT license.
- [Nord](https://github.com/nordtheme/nord/blob/develop/src/nord.styl): Frost / nord8. Copyright Sven Greb; MIT license.

Tomato adapts these accent swatches for its existing graphite surfaces and generates its own interaction colors. These are accent options rather than full ports of the upstream themes. Color references are built in; no network access or additional packages are required at runtime.

## Lucide icon geometry

Some inline icon paths in `app/ui/components.py` are adapted from [Lucide](https://github.com/lucide-icons/lucide), used under the MIT license. Icons render locally with Qt; no remote resources or added runtime dependencies are required.

MIT License

Copyright (c) Lucide Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
