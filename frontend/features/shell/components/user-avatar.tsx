import { getInitials } from "@/lib/shell/initials";
import { cn } from "@/lib/utils";

export type UserAvatarProps = {
  name: string | null;
  email: string;
  className?: string;
};

export function UserAvatar({ name, email, className }: UserAvatarProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid size-8 shrink-0 place-items-center rounded-full bg-petrol-active font-mono text-xs font-semibold text-on-petrol",
        className,
      )}
    >
      {getInitials(name, email)}
    </span>
  );
}
