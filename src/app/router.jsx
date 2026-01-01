import { createBrowserRouter } from "react-router-dom";
import { PublicLayout } from "./layouts/PublicLayout.jsx";
import { AccountLayout } from "./layouts/AccountLayout.jsx";
import { AdminLayout } from "./layouts/AdminLayout.jsx";
import { AuthGuard } from "./guards/AuthGuard.jsx";
import { RoleGuard } from "./guards/RoleGuard.jsx";

// pages
import Home from "../pages/public/Home.jsx";
import ProductList from "../pages/public/ProductList.jsx";
import ProductDetails from "../pages/public/ProductDetails.jsx";
import Categories from "../pages/public/Categories.jsx";
import HowItWorks from "../pages/public/HowItWorks.jsx";
import QuoteRequest from "../pages/public/QuoteRequest.jsx";
import Privacy from "../pages/public/Privacy.jsx";
import Terms from "../pages/public/Terms.jsx";
import Cookies from "../pages/public/Cookies.jsx";
import Login from "../pages/auth/Login.jsx";
import Orders from "../pages/account/Orders.jsx";
import OrderDetails from "../pages/account/OrderDetails.jsx";
import OrderInvoice from "../pages/account/OrderInvoice.jsx";
import SavedQuotes from "../pages/account/SavedQuotes.jsx";
import AdminDashboard from "../pages/admin/AdminDashboard.jsx";
import Signup from "../pages/auth/Signup.jsx";
import SocialComplete from "../pages/auth/SocialComplete.jsx";

export const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/products", element: <ProductList /> },
      { path: "/product/:slug", element: <ProductDetails /> },
      { path: "/categories", element: <Categories /> },
      { path: "/how-it-works", element: <HowItWorks /> },
      { path: "/quote", element: <QuoteRequest /> },
      { path: "/privacy", element: <Privacy /> },
      { path: "/terms", element: <Terms /> },
      { path: "/cookies", element: <Cookies /> },
      { path: "/login", element: <Login /> },
      { path: "/signup", element: <Signup /> },
      { path: "/social-complete", element: <SocialComplete /> },
    ],
  },
  {
    element: <AuthGuard />,
    children: [
      {
        element: <AccountLayout />,
        children: [
          { path: "/account/orders", element: <Orders /> },
          { path: "/account/orders/:id", element: <OrderDetails /> },
          { path: "/account/orders/:id/invoice", element: <OrderInvoice /> },
          { path: "/account/saved-quotes", element: <SavedQuotes /> },
        ],
      },
      {
        element: <RoleGuard allow={["admin", "operator"]} />,
        children: [
          {
            element: <AdminLayout />,
            children: [
              { path: "/admin", element: <AdminDashboard /> },
              // add more admin routes later
            ],
          },
        ],
      },
    ],
  },
]);
