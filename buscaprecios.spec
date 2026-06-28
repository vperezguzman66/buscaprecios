# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["launcher.py"],
    pathex=["backend"],
    binaries=[],
    datas=[
        ("frontend", "frontend"),
    ],
    hiddenimports=[
        # scrapers
        "scrapers",
        "scrapers.base",
        "scrapers.easy",
        "scrapers.homecenter",
        "scrapers.construmart",
        "scrapers.imperial",
        "scrapers.mercadolibre",
        # uvicorn internals
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # asyncio / anyio
        "anyio",
        "anyio._backends._asyncio",
        # fastapi / starlette
        "fastapi",
        "starlette.middleware.base",
        "starlette.staticfiles",
        # slowapi
        "slowapi",
        "slowapi.errors",
        "slowapi.util",
        # httpx
        "httpx",
        "httpcore",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="BuscaPrecios",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon=None,
)
