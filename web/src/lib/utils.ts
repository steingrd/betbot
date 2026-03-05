import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const marketLabels: Record<string, string> = {
  Home: 'Hjemme',
  Away: 'Borte',
  Draw: 'Uavgjort',
  Hjemmeseier: 'Hjemme',
  Borteseier: 'Borte',
}

export function translateMarket(market: string): string {
  return marketLabels[market] ?? market
}
