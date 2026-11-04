import { useCallback, useEffect, useRef, useState } from "react";

import { fetchReviewQueue, postponeReview } from "../services/reviews.ts";
import type { ReviewQueue } from "../types/review.ts";
import { getErrorMessage } from "../utils/apiError.ts";

export function useReviewQueue() {
  const [queue, setQueue] = useState<ReviewQueue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [postponingId, setPostponingId] = useState<number | null>(null);
  const requestId = useRef(0);

  const load = useCallback((id: number) => {
    fetchReviewQueue()
      .then((data) => {
        if (requestId.current !== id) {
          return;
        }
        setQueue(data);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (requestId.current !== id) {
          return;
        }
        setError(getErrorMessage(reason, "读取复习队列失败"));
      });
  }, []);

  const reload = useCallback(() => {
    const id = requestId.current + 1;
    requestId.current = id;
    setError(null);
    load(id);
  }, [load]);

  useEffect(() => {
    const id = requestId.current + 1;
    requestId.current = id;
    load(id);
  }, [load]);

  const postpone = useCallback(
    async (scheduleId: number) => {
      setPostponingId(scheduleId);
      setError(null);
      try {
        await postponeReview(scheduleId, 1);
        const id = requestId.current + 1;
        requestId.current = id;
        load(id);
      } catch (reason: unknown) {
        setError(getErrorMessage(reason, "推迟复习失败"));
      } finally {
        setPostponingId(null);
      }
    },
    [load],
  );

  return {
    queue,
    loading: queue === null && error === null,
    error,
    reload,
    postpone,
    postponingId,
  };
}
