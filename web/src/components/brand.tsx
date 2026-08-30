import Image from "next/image";
import Link from "next/link";

type BrandProps = {
  className?: string;
  short?: boolean;
};

export function Brand({ className = "", short = false }: BrandProps) {
  return (
    <Link
      className={["brand", className].filter(Boolean).join(" ")}
      href="/"
      aria-label="Kuma Voice home"
    >
      <span className="brand-mark" aria-hidden="true">
        <Image
          src="/kumavoice-mark.svg"
          alt=""
          width={40}
          height={23}
          loading="eager"
        />
      </span>
      <span className="brand-name">
        Kuma{!short && <> <span>Voice</span></>}
      </span>
    </Link>
  );
}
