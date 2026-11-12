# FFHelper

A local, screen-reading assistant for FFXIV raids, built in two layers:

- **Radar (fast):** OCRs the boss cast bar about 10 times a second, looks the cast up in your own JSON callout files, and speaks the callout right away ("Stack and mitigate"). Each read takes about 20 ms on the CPU.
- **Coach (slow):** every few seconds, a local vision model (Qwen2.5-VL running in Ollama on your GPU) looks at your hotbars, buffs and job gauge and screams abuse at you, drill-sergeant style, on every check, and tells you the fix when you mess up ("Use Afflatus Misery, you lily-hoarding dipshit!"). It only mocks your gameplay. Mechanic callouts from the radar stay clean.

Everything runs on your PC. FFHelper only looks at the screen. It never reads game memory or sends inputs. Any third-party tool still breaks the FFXIV User Agreement, so use it at your own risk.

## Setup (Windows)

To install it like a normal app, see [Windows installer](#windows-installer). To run it from source:

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/). uv installs Python for you.
2. Install [Ollama](https://ollama.com/download). FFHelper starts it if it isn't already running. The coach downloads its model (`qwen2.5vl:7b`, about 6 GB) the first time it runs. It fits easily in 16 GB of VRAM alongside the game.
3. In this folder, run `uv sync`.
4. In FFXIV, open System Configuration > Display Settings and set Screen Mode to **Borderless Windowed**. Screen capture can come back black in exclusive full screen.

## Use

```
uv run ffhelper calibrate     # you get 3 s to switch to the game, then drag a box for each region
uv run ffhelper run           # Ctrl+C to stop
uv run ffhelper run --debug   # also logs every OCR read and its timing
```

Settings are in `config.toml`, which is created from `config.example.toml` the first time you run FFHelper. That's where you set your job, coach notes, model and timings.

## Callouts

FFHelper comes with `mechanics/fru.json`: Futures Rewritten (Ultimate) callouts for a White Mage. Each callout has a spoken `say` and a longer `note` for you to read. Edit the `say` texts to match your static's strats and mitigation plan.

The radar only reads the cast bar of your current target. Casts by enemies you can't target (P1 clones, P2 mirrors and Oracle's Reflection, P4 Fragment of Fate) never show there, so they're described in the `note` of the boss cast before them. In P4, only the boss you have targeted is called.

To add another fight, put another JSON file in `mechanics/`. Write cast names exactly as the boss cast bar shows them. Small OCR mistakes are tolerated.

```json
{
  "fight": "Savage floor 1",
  "mechanics": {
    "Akh Morn": { "say": "Stack and mitigate", "note": "Feint, Addle, Reprisal" },
    "Exaflare": "Move"
  }
}
```

## Windows installer

`packaging\build.ps1` builds `dist\FFHelper-Setup-<version>.exe`, a normal installer with Python and every dependency bundled. Run it on the Windows PC, after installing uv and Inno Setup (`winget install JRSoftware.InnoSetup`):

```
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

The installer:

- installs for your Windows user only, so there's no admin prompt;
- adds Start menu shortcuts for **FFHelper**, **Calibrate screen regions**, **Edit settings** and **Callouts folder**;
- offers to download and install Ollama if it's missing;
- keeps your settings and callouts in `%APPDATA%\FFHelper`, so upgrades and uninstalls never touch them.

The installer isn't code-signed, so Windows SmartScreen warns the first time you run it: choose **More info > Run anyway**.

## Tests

```
uv run pytest
```
