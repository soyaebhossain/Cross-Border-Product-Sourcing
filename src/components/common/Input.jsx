export default function Input({ className = "", ...props }) {
  return (
    <input
      className={"w-full px-3 py-2 rounded-xl border bg-white outline-none focus:ring-2 " + className}
      {...props}
    />
  );
}
