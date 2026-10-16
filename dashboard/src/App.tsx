import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { MotionConfig } from "motion/react";
import { useLiveStatus, useStatus } from "./api/hooks";
import { Shell } from "./components/Shell";
import { ToastProvider } from "./components/Toast";
import Offline from "./pages/Offline";
import Today from "./pages/Today";
import Timeline from "./pages/Timeline";
import Review from "./pages/Review";
import Memory from "./pages/Memory";
import CV from "./pages/CV";

// Less-visited screens load on demand to keep the first paint light.
const Insights = lazy(() => import("./pages/Insights"));
const Settings = lazy(() => import("./pages/Settings"));
const Onboarding = lazy(() => import("./pages/Onboarding"));

function Gate() {
  const status = useStatus();
  useLiveStatus();

  if (status.isError) return <Offline />;
  if (!status.data) return <div className="boot" aria-busy="true" />;
  if (!status.data.profile_complete)
    return (
      <Suspense fallback={<div className="boot" />}>
        <Onboarding />
      </Suspense>
    );
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<Today />} />
          <Route path="timeline" element={<Timeline />} />
          <Route path="review" element={<Review />} />
          <Route path="memory" element={<Memory />} />
          <Route path="insights" element={<Insights />} />
          <Route path="cv" element={<CV />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Today />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <ToastProvider>
        <Gate />
      </ToastProvider>
    </MotionConfig>
  );
}
