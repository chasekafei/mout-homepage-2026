import { useLayoutEffect } from "react";

const BOTTOM_TOLERANCE = 24;
const POSITION_EPSILON = 2;

/** Follow document growth until the reader scrolls away from the latest message. */
export function usePageBottomFollow(conversationId: string | undefined, enabled: boolean) {
  useLayoutEffect(() => {
    if (!enabled) return;

    let following = true;
    let frame: number | null = null;
    let touchY: number | null = null;
    let viewportWidth = window.innerWidth;
    let viewportHeight = window.innerHeight;
    let viewportChanged = false;
    const maxScrollY = () => Math.max(0, (document.scrollingElement ?? document.documentElement).scrollHeight - window.innerHeight);
    const position = () => Math.max(0, Math.min(window.scrollY, maxScrollY()));
    const bottomGap = () => maxScrollY() - position();
    let lastScrollY = position();

    const cancelScroll = () => {
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null;
    };
    const scrollToBottom = () => {
      const target = maxScrollY();
      if (Math.abs(window.scrollY - target) > 1) window.scrollTo({ top: target, behavior: "instant" });
      lastScrollY = position();
    };
    const queueScroll = () => {
      if (!following || frame !== null) return;
      frame = requestAnimationFrame(() => {
        frame = null;
        // Input may have paused follow after this frame was queued.
        if (!following) return;
        // A scrollbar/keyboard scroll can move the document before its scroll
        // event is delivered. Do not pull it back in that intervening frame.
        if (!viewportChanged && position() < lastScrollY - 1 && bottomGap() > POSITION_EPSILON) {
          pause();
          lastScrollY = position();
          return;
        }
        scrollToBottom();
        viewportChanged = false;
      });
    };
    const pause = () => {
      // An upward gesture on a page that still fits must not strand follow.
      if (maxScrollY() <= POSITION_EPSILON) return;
      following = false;
      viewportChanged = false;
      cancelScroll();
    };
    const resumeAtBottom = () => {
      if (bottomGap() > BOTTOM_TOLERANCE) return;
      following = true;
      lastScrollY = position();
      queueScroll();
    };
    const onResize = () => {
      viewportWidth = window.innerWidth;
      viewportHeight = window.innerHeight;
      viewportChanged = following;
      lastScrollY = position();
      queueScroll();
    };
    const onScroll = () => {
      if (window.innerWidth !== viewportWidth || window.innerHeight !== viewportHeight) onResize();
      const y = position();
      const delta = y - lastScrollY;
      lastScrollY = y;
      if (bottomGap() <= POSITION_EPSILON) {
        following = true;
        queueScroll();
        return;
      }
      if (following && viewportChanged) { queueScroll(); return; }
      // Ignore the browser clamping scrollY after the viewport/content shrinks.
      if (delta < -1 && bottomGap() > POSITION_EPSILON) pause();
      else if (delta > 0) resumeAtBottom();
    };
    const onWheel = (event: WheelEvent) => {
      if (event.ctrlKey) return; // A zoom gesture is not a reading gesture.
      if (event.deltaY < 0) pause();
      else if (event.deltaY > 0) resumeAtBottom();
    };
    const onTouchStart = (event: TouchEvent) => {
      touchY = event.touches.length === 1 ? event.touches[0].clientY : null;
    };
    const onTouchMove = (event: TouchEvent) => {
      const y = event.touches.length === 1 ? event.touches[0].clientY : null;
      if (y !== null && touchY !== null) {
        if (y > touchY) pause();
        else if (y < touchY) resumeAtBottom();
      }
      touchY = y;
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.target instanceof Element && event.target.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])")) return;
      if (["ArrowUp", "PageUp", "Home"].includes(event.key) || (event.key === " " && event.shiftKey)) pause();
      else if (event.key === "End" && !event.shiftKey) {
        event.preventDefault();
        following = true;
        cancelScroll();
        scrollToBottom();
      }
      else if (["ArrowDown", "PageDown", " "].includes(event.key)) resumeAtBottom();
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("wheel", onWheel, { passive: true });
    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchmove", onTouchMove, { passive: true });
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", onResize);
    window.visualViewport?.addEventListener("resize", onResize);
    const observer = new ResizeObserver(queueScroll);
    observer.observe(document.body);
    queueScroll();

    return () => {
      cancelScroll();
      observer.disconnect();
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", onResize);
      window.visualViewport?.removeEventListener("resize", onResize);
    };
  }, [conversationId, enabled]);
}
