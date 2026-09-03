import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import PlaybookRun from "./pages/PlaybookRun";
import MemoView from "./pages/MemoView";
import FanExplorer from "./pages/FanExplorer";
import EmptyState from "./components/EmptyState";

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/run/:playbook/:entityId" element={<PlaybookRun />} />
        <Route path="/memo/:memoId" element={<MemoView />} />
        <Route path="/explore/:entityId" element={<FanExplorer />} />
        <Route
          path="*"
          element={
            <EmptyState
              title="Page not found"
              detail="That reel isn't in the can. Head back to search."
            />
          }
        />
      </Routes>
    </Layout>
  );
}

export default App;
