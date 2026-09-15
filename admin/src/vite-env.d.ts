/// <reference types="vite/client" />

// フォルダ選択に使う属性。React の型定義には含まれないため、ここで補う。
declare module "react" {
  interface InputHTMLAttributes<T> {
    webkitdirectory?: string;
  }
}

export {};
