import { useCallback, useEffect, useRef, useState } from 'react';

interface ChatRequestState {
  loading: boolean;
  stepIndex: number;
  error: string | null;
  controller: AbortController | null;
}

const STEPS = ['分析问题...', '检索知识库...', '生成回答...'];

export function useChatRequestState() {
  const [state, setState] = useState<ChatRequestState>({
    loading: false,
    stepIndex: 0,
    error: null,
    controller: null,
  });
  const timerRef = useRef<number | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => () => clearTimer(), [clearTimer]);

  const start = useCallback(() => {
    clearTimer();
    const controller = new AbortController();
    setState({
      loading: true,
      stepIndex: 0,
      error: null,
      controller,
    });
    timerRef.current = window.setInterval(() => {
      setState(prev => ({
        ...prev,
        stepIndex: prev.stepIndex + 1 < STEPS.length ? prev.stepIndex + 1 : prev.stepIndex,
      }));
    }, 1200);
    return controller;
  }, [clearTimer]);

  const finish = useCallback(() => {
    clearTimer();
    setState(prev => ({ ...prev, loading: false, controller: null }));
  }, [clearTimer]);

  const fail = useCallback((error: string) => {
    clearTimer();
    setState(prev => ({ ...prev, loading: false, error, controller: null }));
  }, [clearTimer]);

  return {
    ...state,
    steps: STEPS,
    start,
    finish,
    fail,
  };
}
