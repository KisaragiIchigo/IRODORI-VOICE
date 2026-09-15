import * as Label from "@radix-ui/react-label";
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { useId } from "react";

import { cn } from "../../../lib/cn";

const CONTROL = cn(
  "w-full rounded-md border border-white/[0.06] bg-black/40 px-3 py-2",
  "text-body text-paper-200 placeholder:text-paper-500",
  "shadow-inset transition-colors",
  "focus:border-beni/50 focus:outline-none",
);

type FieldProps = {
  label: string;
  /** 補足説明。読めない小ささにはしない。 */
  hint?: ReactNode;
  children: ReactNode;
};

export function Field({ label, hint, children }: FieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="label-caps">{label}</span>
      {children}
      {hint ? <p className="text-label text-paper-400">{hint}</p> : null}
    </div>
  );
}

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: ReactNode;
};

export function TextField({ label, hint, className, ...rest }: TextFieldProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <Label.Root htmlFor={id} className="label-caps">
        {label}
      </Label.Root>
      <input id={id} className={cn(CONTROL, className)} {...rest} />
      {hint ? <p className="text-label text-paper-400">{hint}</p> : null}
    </div>
  );
}

type TextAreaFieldProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  hint?: ReactNode;
};

export function TextAreaField({ label, hint, className, ...rest }: TextAreaFieldProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <Label.Root htmlFor={id} className="label-caps">
        {label}
      </Label.Root>
      <textarea id={id} className={cn(CONTROL, "resize-y leading-relaxed", className)} {...rest} />
      {hint ? <p className="text-label text-paper-400">{hint}</p> : null}
    </div>
  );
}

type SelectFieldProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  hint?: ReactNode;
};

export function SelectField({
  label,
  hint,
  className,
  children,
  ...rest
}: SelectFieldProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <Label.Root htmlFor={id} className="label-caps">
        {label}
      </Label.Root>
      <select
        id={id}
        className={cn(CONTROL, rest.disabled && "opacity-40", className)}
        {...rest}
      >
        {children}
      </select>
      {hint ? <p className="text-label text-paper-400">{hint}</p> : null}
    </div>
  );
}
