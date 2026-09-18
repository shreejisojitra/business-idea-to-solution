/**
 * Module 22 — useSpeechRecognition
 * Browser-native Web Speech API hook.
 * Supports: English (en-IN), Hindi (hi-IN), Gujarati (gu-IN).
 * NO Text-to-Speech. NO audio storage. NO paid API. NO auto-send.
 */
import { useState, useRef, useCallback, useEffect } from 'react';

export const SPEECH_LANGUAGES = [
    { code: 'en-IN', label: 'English' },
    { code: 'hi-IN', label: 'Hindi' },
    { code: 'gu-IN', label: 'Gujarati' },
];

export const SPEECH_STATES = {
    IDLE: 'IDLE',
    LISTENING: 'LISTENING',
    STOPPED: 'STOPPED',
    ERROR: 'ERROR',
};

const ERROR_MESSAGES = {
    'not-allowed': 'Microphone permission was denied. You can continue using text input.',
    'audio-capture': 'No microphone was found. Please connect a microphone and try again.',
    'no-speech': 'No speech was detected. Please try speaking again.',
    'network': 'A network error occurred during speech recognition. Please check your connection.',
    'aborted': 'Speech recognition was stopped.',
    'service-not-allowed': 'Speech recognition service is not allowed. Please check browser settings.',
    'language-not-supported': 'The selected language is not supported by your browser.',
};

export function isSpeechSupported() {
    return !!(
        typeof window !== 'undefined' &&
        (window.SpeechRecognition || window.webkitSpeechRecognition)
    );
}

/**
 * @param {object} opts
 * @param {string} opts.lang - BCP-47 tag e.g. 'en-IN', 'hi-IN', 'gu-IN'
 * @param {function} opts.onResult - called with final transcript string
 * @param {function} opts.onInterim - called with interim transcript string
 */
export function useSpeechRecognition({ lang = 'en-IN', onResult, onInterim } = {}) {
    const [speechState, setSpeechState] = useState(SPEECH_STATES.IDLE);
    const [errorMessage, setErrorMessage] = useState('');
    const [interimText, setInterimText] = useState('');
    const recognitionRef = useRef(null);
    const isSupported = isSpeechSupported();

    const stopRecognition = useCallback(() => {
        if (recognitionRef.current) {
            try { recognitionRef.current.stop(); } catch (_) {}
            recognitionRef.current = null;
        }
        setInterimText('');
        setSpeechState(SPEECH_STATES.IDLE);
    }, []);

    // Cleanup on unmount or project/logout change
    useEffect(() => {
        return () => {
            if (recognitionRef.current) {
                try { recognitionRef.current.stop(); } catch (_) {}
                recognitionRef.current = null;
            }
        };
    }, []);

    const startRecognition = useCallback(() => {
        if (!isSupported) {
            setErrorMessage('Speech input is not supported in this browser. You can continue using text input.');
            setSpeechState(SPEECH_STATES.ERROR);
            return;
        }

        setErrorMessage('');
        setInterimText('');

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();

        recognition.lang = lang;
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
            setSpeechState(SPEECH_STATES.LISTENING);
            setErrorMessage('');
        };

        recognition.onresult = (event) => {
            let interim = '';
            let final = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    final += transcript;
                } else {
                    interim += transcript;
                }
            }
            if (interim) {
                setInterimText(interim);
                if (onInterim) onInterim(interim);
            }
            if (final) {
                setInterimText('');
                if (onResult) onResult(final);
            }
        };

        recognition.onerror = (event) => {
            const msg = ERROR_MESSAGES[event.error] ||
                'Speech recognition encountered an error. Please try again.';
            setErrorMessage(msg);
            setSpeechState(SPEECH_STATES.ERROR);
            recognitionRef.current = null;
            setInterimText('');
        };

        recognition.onend = () => {
            recognitionRef.current = null;
            setInterimText('');
            setSpeechState((prev) =>
                prev === SPEECH_STATES.LISTENING ? SPEECH_STATES.STOPPED : prev
            );
        };

        recognitionRef.current = recognition;
        try {
            recognition.start();
        } catch (_) {
            setErrorMessage('Could not start speech recognition. Please try again.');
            setSpeechState(SPEECH_STATES.ERROR);
            recognitionRef.current = null;
        }
    }, [isSupported, lang, onResult, onInterim]);

    const toggleRecognition = useCallback(() => {
        if (speechState === SPEECH_STATES.LISTENING) {
            stopRecognition();
        } else {
            startRecognition();
        }
    }, [speechState, startRecognition, stopRecognition]);

    return {
        speechState,
        errorMessage,
        interimText,
        isSupported,
        toggleRecognition,
        stopRecognition,
    };
}
