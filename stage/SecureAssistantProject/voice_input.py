"""Local, one-shot voice input using the Windows speech-recognition engine."""

import subprocess


LISTEN_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech

try {
    $culture = New-Object System.Globalization.CultureInfo('fr-FR')
    $recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
} catch {
    # Use the installed default recognizer when the French speech pack is unavailable.
    $recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine
}

$recognizer.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$recognizer.SetInputToDefaultAudioDevice()
$result = $recognizer.Recognize([TimeSpan]::FromSeconds(12))

if ($null -eq $result -or [string]::IsNullOrWhiteSpace($result.Text)) {
    exit 2
}

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output $result.Text
'''


def listen_once(timeout_seconds=20):
    """Return one locally transcribed sentence, or raise a readable error."""
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", LISTEN_SCRIPT],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as error:
        raise RuntimeError("Windows PowerShell is required for voice input.") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("No voice command was detected before the listening timeout.") from error

    transcript = completed.stdout.strip()
    if transcript:
        return transcript

    details = completed.stderr.strip()
    if details:
        raise RuntimeError(f"Voice recognition is unavailable: {details}")
    raise RuntimeError(
        "No voice command was detected. Check that the microphone is enabled and try again."
    )
