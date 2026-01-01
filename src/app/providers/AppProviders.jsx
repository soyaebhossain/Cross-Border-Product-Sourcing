import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppHydrate } from "./AppHydrate";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

export function AppProviders({ children }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AppHydrate>{children}</AppHydrate>
    </QueryClientProvider>
  );
}
