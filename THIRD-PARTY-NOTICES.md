# Third-party components

BarcodeBuddy installs these open-source libraries from the Python Package Index. Each one is used under its own license, listed here as published by its authors for the exact version in constraints.txt. Windows installs may also add small platform helpers (for example tzdata and colorama) under their own licenses.

| Library | Version | License |
| --- | --- | --- |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| APScheduler | 3.11.3 | MIT License |
| bcrypt | 5.0.0 | Apache Software License |
| certifi | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) |
| cffi | 2.1.1 | MIT-0 |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| fastapi | 0.142.2 | MIT |
| h11 | 0.16.0 | MIT License |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD License |
| idna | 3.20 | BSD-3-Clause |
| markdown-it-py | 4.2.0 | MIT License |
| mdurl | 0.1.2 | MIT License |
| numpy | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| opencv-python-headless | 5.0.0.93 | Apache Software License |
| opentelemetry-api | 1.45.1 | Apache-2.0 |
| pillow | 12.3.0 | MIT-CMU |
| prometheus_client | 0.26.0 | Apache-2.0 AND BSD-2-Clause |
| pycparser | 3.0 | BSD-3-Clause |
| pydantic | 2.13.5 | MIT |
| pydantic_core | 2.46.5 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| PyJWT | 2.15.1 | MIT |
| pypdfium2 | 5.14.0 | BSD-3-Clause, Apache-2.0, dependency licenses |
| python-multipart | 0.0.32 | Apache-2.0 |
| reportlab | 5.0.1 | BSD License |
| rich | 15.0.0 | MIT License |
| SQLAlchemy | 2.1.3 | MIT |
| starlette | 1.7.0 | BSD-3-Clause |
| structlog | 26.1.0 | MIT OR Apache-2.0 |
| tenacity | 9.2.1 | Apache-2.0 |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| tzlocal | 5.4.4 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| watchfiles | 1.3.0 | MIT License |
| zxing-cpp | 3.1.1 | Apache-2.0 |

## Copyleft

None of these libraries is under a strong copyleft license such as the GPL or AGPL. PDF pages are read with PDFium through pypdfium2 (BSD-3-Clause and Apache-2.0) and reports are written with ReportLab (BSD). PDFium's bundled components carry their own notices inside the pypdfium2 package (licenses folder): FreeType is used under its FreeType License option, and ICU's notice quotes the GPL only for build scripts covered by the Autoconf exception, which are not part of the installed library. certifi is under the Mozilla Public License 2.0, which applies to its own files only. tests/test_dependency_licenses.py fails the build if a GPL or AGPL library is added.
