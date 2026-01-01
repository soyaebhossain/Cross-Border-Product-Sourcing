export default function Card({ children, className = "" }) {
  return <div className={"bg-white border rounded-2xl p-4 shadow-sm " + className}>{children}</div>;
}
