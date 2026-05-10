import { useEffect, useRef, useCallback } from 'react'

/**
 * Polls an async function every `interval` ms until `shouldStop` returns true.
 */
export function usePolling(fn, interval = 3000, shouldStop) {
  const timer = useRef(null)
  const fnRef = useRef(fn)
  const stopRef = useRef(shouldStop)

  fnRef.current = fn
  stopRef.current = shouldStop

  const start = useCallback(() => {
    const tick = async () => {
      await fnRef.current()
      if (!stopRef.current?.()) {
        timer.current = setTimeout(tick, interval)
      }
    }
    tick()
  }, [interval])

  const stop = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
  }, [])

  useEffect(() => () => stop(), [stop])

  return { start, stop }
}
