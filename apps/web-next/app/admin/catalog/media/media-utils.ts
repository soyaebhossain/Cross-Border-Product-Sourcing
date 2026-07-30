const blockedPlaceholderHosts = new Set([
  "loremflickr.com",
  "www.loremflickr.com",
  "picsum.photos",
  "source.unsplash.com",
]);

export function hasAssignedProductImage(image: string | null | undefined) {
  const value = image?.trim();
  if (!value) return false;
  return validateProductImageLocation(value) === "";
}

export function validateProductImageLocation(value: string) {
  const location = value.trim();
  if (!location) return "Add an HTTPS image URL or a local /media/products/ path.";
  if (/[\u0000-\u001f\u007f]/.test(location)) return "The image location contains unsupported characters.";

  if (location.startsWith("/")) {
    if (location.startsWith("//")) return "Protocol-relative URLs are not accepted. Use a complete HTTPS URL.";
    if (location.includes("\\") || location.split("/").includes("..")) {
      return "Use a safe absolute public path without backslashes or parent-directory segments.";
    }
    if (!/^\/media\/products\/[A-Za-z0-9][A-Za-z0-9/_-]*\.(?:avif|gif|jpe?g|png|webp)$/i.test(location)) {
      return "Local product images must use a safe /media/products/ path and a supported image extension.";
    }
    return "";
  }

  let url: URL;
  try {
    url = new URL(location);
  } catch {
    return "Enter a complete HTTPS URL or a local path beginning with /.";
  }

  if (url.username || url.password) return "Image URLs must not contain credentials.";
  if (blockedPlaceholderHosts.has(url.hostname.toLowerCase())) {
    return "Random placeholder services are unreliable. Use an owned, licensed or supplier-approved image.";
  }

  const localDevelopmentHost = url.hostname === "localhost" || url.hostname === "127.0.0.1";
  if (url.protocol !== "https:" && !(url.protocol === "http:" && localDevelopmentHost)) {
    return "Remote product images must use HTTPS.";
  }
  return "";
}
