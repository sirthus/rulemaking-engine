import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { LoadingView } from "./components/LoadingView";

const HomePage = lazy(() => import("./pages/HomePage"));
const DocketPage = lazy(() => import("./pages/DocketPage"));
const CardDetailPage = lazy(() => import("./pages/CardDetailPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

export default function App() {
  return (
    <Suspense fallback={<LoadingView label="Loading page" />}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/dockets/:docketId" element={<DocketPage />} />
        <Route path="/dockets/:docketId/cards/:cardId" element={<CardDetailPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}
