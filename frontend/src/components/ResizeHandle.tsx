import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * A thin drag-to-resize splitter. Designed to sit on a single edge of a
 * sibling pane — the parent owns the pane's size, this component merely
 * emits deltas as the user drags.
 *
 *   edge = 'right'  | 'left'  → horizontal resize (adjusts width)
 *   edge = 'top'    | 'bottom'→ vertical   resize (adjusts height)
 *
 * The handle is a 1px visible border with a ±3px invisible hit area
 * extending outwards, which is the standard VSCode / Cursor feel — easy
 * to grab without being visually heavy.
 */
type Edge = 'left' | 'right' | 'top' | 'bottom'

interface Props {
  edge: Edge
  /**
   * Called on every pointermove during a drag. `px` is the current
   * CURSOR POSITION on the axis of interest (clientX for horizontal,
   * clientY for vertical). The consumer converts that to a pane size
   * by comparing against the pane's current bounding rect — doing it
   * this way avoids accumulated-delta drift when the cursor leaves the
   * pane or re-enters it.
   */
  onResize: (px: number) => void
  /** Fires once at pointerup so consumers can persist the final size. */
  onResizeEnd?: () => void
  /** Accessible label e.g. "Resize node palette". */
  ariaLabel?: string
}

export default function ResizeHandle({ edge, onResize, onResizeEnd, ariaLabel }: Props) {
  const [hover, setHover] = useState(false)
  const [dragging, setDragging] = useState(false)
  const draggingRef = useRef(false)

  const isHorizontal = edge === 'left' || edge === 'right'
  const cursor = isHorizontal ? 'col-resize' : 'row-resize'

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.preventDefault()
      ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
      draggingRef.current = true
      setDragging(true)

      // Lock page-wide cursor + disable text selection while dragging.
      document.body.style.cursor = cursor
      document.body.style.userSelect = 'none'
    },
    [cursor],
  )

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!draggingRef.current) return
      onResize(isHorizontal ? e.clientX : e.clientY)
    },
    [isHorizontal, onResize],
  )

  const handlePointerUp = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!draggingRef.current) return
      draggingRef.current = false
      setDragging(false)
      try {
        ;(e.target as HTMLElement).releasePointerCapture(e.pointerId)
      } catch {
        /* pointer already released */
      }
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      onResizeEnd?.()
    },
    [onResizeEnd],
  )

  // Safety net: if the pointer is released outside the element (which is
  // rare with pointer capture but can happen on window-level blurs),
  // unwind the drag state.
  useEffect(() => {
    if (!dragging) return
    const up = () => {
      draggingRef.current = false
      setDragging(false)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      onResizeEnd?.()
    }
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', up)
    return () => {
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', up)
    }
  }, [dragging, onResizeEnd])

  // Position the handle just inside the specified edge so it overlaps
  // the pane's border. The hit area is expanded a few px beyond the
  // visible 1px line for grabability.
  const base: React.CSSProperties = {
    position: 'absolute',
    cursor,
    zIndex: 20,
    touchAction: 'none',
    background: 'transparent',
    transition: 'background-color 120ms ease',
  }

  const lineColor =
    dragging ? 'var(--accent, #0ea5e9)' : hover ? 'color-mix(in srgb, var(--accent, #0ea5e9) 60%, transparent)' : 'transparent'

  let placement: React.CSSProperties
  if (edge === 'right') {
    placement = { top: 0, bottom: 0, right: -3, width: 7, borderRight: `1px solid ${lineColor}` }
  } else if (edge === 'left') {
    placement = { top: 0, bottom: 0, left: -3, width: 7, borderLeft: `1px solid ${lineColor}` }
  } else if (edge === 'top') {
    placement = { left: 0, right: 0, top: -3, height: 7, borderTop: `1px solid ${lineColor}` }
  } else {
    placement = { left: 0, right: 0, bottom: -3, height: 7, borderBottom: `1px solid ${lineColor}` }
  }

  return (
    <div
      role="separator"
      aria-label={ariaLabel}
      aria-orientation={isHorizontal ? 'vertical' : 'horizontal'}
      style={{ ...base, ...placement }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    />
  )
}
