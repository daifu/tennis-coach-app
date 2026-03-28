import React from "react";
// Minimal stub for next/image — renders a plain <img> in tests.
const Image = ({ src, alt, ...rest }: React.ImgHTMLAttributes<HTMLImageElement> & { fill?: boolean; sizes?: string }) => (
  // eslint-disable-next-line @next/next/no-img-element
  <img src={src} alt={alt} {...rest} />
);
export default Image;
