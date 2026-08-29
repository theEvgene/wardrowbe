'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { useTranslations } from 'next-intl';
import {
  Briefcase,
  Shirt,
  Heart,
  Dumbbell,
  TreePine,
  Sparkles,
  RefreshCw,
  ThumbsUp,
  ThumbsDown,
  Cloud,
  Sun,
  CloudRain,
  Loader2,
  Thermometer,
  Droplets,
  MapPin,
  Wind,
  GlassWater,
  Cloudy,
  CloudSun,
  Snowflake,
  CalendarDays,
  CloudLightning,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { api, setAccessToken } from '@/lib/api';
import { Item, Outfit, StyleBatchResponse } from '@/lib/types';
import { useOccasions } from '@/lib/hooks/use-translated-constants';
import { useWeather, Weather } from '@/lib/hooks/use-weather';
import { usePreferences } from '@/lib/hooks/use-preferences';
import { cn } from '@/lib/utils';
import { TempUnit, formatTemp, displayValue } from '@/lib/temperature';
import { DetectedStyleSelector } from '@/components/detected-style-selector';
import { OutfitCompositePreview } from '@/components/outfit-composite-preview';
import { buildStyleBatchRequest, getStyleDateBounds } from '@/lib/style-outfits';
import { StyleGenerationError } from '@/components/style-generation-error';
import { ItemPicker } from '@/components/shared/item-picker';

type Translator = (key: string, values?: Record<string, string | number>) => string;

// Map occasion values to icons and colors
const OCCASION_CONFIG: Record<string, { icon: React.ReactNode; color: string }> = {
  casual: { icon: <Shirt className="h-4 w-4" />, color: 'hover:border-blue-400 hover:bg-blue-50 data-[selected=true]:border-blue-500 data-[selected=true]:bg-blue-50 data-[selected=true]:text-blue-700' },
  office: { icon: <Briefcase className="h-4 w-4" />, color: 'hover:border-slate-400 hover:bg-slate-50 data-[selected=true]:border-slate-500 data-[selected=true]:bg-slate-50 data-[selected=true]:text-slate-700' },
  formal: { icon: <GlassWater className="h-4 w-4" />, color: 'hover:border-purple-400 hover:bg-purple-50 data-[selected=true]:border-purple-500 data-[selected=true]:bg-purple-50 data-[selected=true]:text-purple-700' },
  date: { icon: <Heart className="h-4 w-4" />, color: 'hover:border-rose-400 hover:bg-rose-50 data-[selected=true]:border-rose-500 data-[selected=true]:bg-rose-50 data-[selected=true]:text-rose-700' },
  sporty: { icon: <Dumbbell className="h-4 w-4" />, color: 'hover:border-orange-400 hover:bg-orange-50 data-[selected=true]:border-orange-500 data-[selected=true]:bg-orange-50 data-[selected=true]:text-orange-700' },
  outdoor: { icon: <TreePine className="h-4 w-4" />, color: 'hover:border-green-400 hover:bg-green-50 data-[selected=true]:border-green-500 data-[selected=true]:bg-green-50 data-[selected=true]:text-green-700' },
};

// Weather condition to icon mapping
function getWeatherIcon(condition: string, isDay: boolean) {
  const c = condition.toLowerCase();
  if (c.includes('rain') || c.includes('drizzle')) return <CloudRain className="h-8 w-8" />;
  if (c.includes('snow')) return <Snowflake className="h-8 w-8" />;
  if (c.includes('thunder') || c.includes('storm')) return <CloudLightning className="h-8 w-8" />;
  if (c.includes('cloud') && c.includes('part')) return <CloudSun className="h-8 w-8" />;
  if (c.includes('cloud') || c.includes('overcast')) return <Cloudy className="h-8 w-8" />;
  return isDay ? <Sun className="h-8 w-8" /> : <Cloud className="h-8 w-8" />;
}

// Get time-based greeting key
function getGreetingKey(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'greeting.morning';
  if (hour < 17) return 'greeting.afternoon';
  return 'greeting.evening';
}

// Get weather-based outfit hint key
function getWeatherHintKey(weather: Weather): string {
  const temp = weather.temperature;
  const condition = weather.condition.toLowerCase();

  if (weather.precipitation_chance > 50) return 'weatherHints.rainy';
  if (temp < 10) return 'weatherHints.cold';
  if (temp < 18) return 'weatherHints.mild';
  if (temp > 28) return 'weatherHints.hot';
  if (condition.includes('wind')) return 'weatherHints.windy';
  return 'weatherHints.nice';
}

function WeatherCard({ weather, isLoading, temperatureUnit, t }: { weather?: Weather; isLoading: boolean; temperatureUnit: TempUnit; t: Translator }) {
  if (isLoading) {
    return (
      <Card className="border-muted">
        <CardContent className="p-6">
          <div className="flex items-center gap-4">
            <Skeleton className="h-16 w-16 rounded-full" />
            <div className="space-y-2">
              <Skeleton className="h-8 w-24" />
              <Skeleton className="h-4 w-32" />
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!weather) {
    return (
      <Card className="border-dashed">
        <CardContent className="p-6">
          <div className="flex items-center gap-4">
            <div className="h-14 w-14 rounded-full bg-muted flex items-center justify-center">
              <MapPin className="h-6 w-6 text-muted-foreground" />
            </div>
            <div>
              <p className="font-medium">{t('location.notSet')}</p>
              <p className="text-sm text-muted-foreground">
                {t('location.setDescription')}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="h-14 w-14 rounded-full bg-muted flex items-center justify-center text-foreground">
              {getWeatherIcon(weather.condition, weather.is_day)}
            </div>
            <div>
              <div className="flex items-baseline gap-1">
                <span className="text-4xl font-semibold tracking-tight">{displayValue(weather.temperature, temperatureUnit)}</span>
                <span className="text-lg text-muted-foreground">{temperatureUnit === 'fahrenheit' ? '°F' : '°C'}</span>
              </div>
              <p className="text-sm text-muted-foreground capitalize">{weather.condition}</p>
            </div>
          </div>
          <div className="text-right text-sm text-muted-foreground space-y-1">
            <div className="flex items-center gap-1.5 justify-end">
              <Thermometer className="h-3.5 w-3.5" />
              <span>{t('weather.feelsLike', { temp: displayValue(weather.feels_like, temperatureUnit) })}</span>
            </div>
            <div className="flex items-center gap-1.5 justify-end">
              <Droplets className="h-3.5 w-3.5" />
              <span>{t('weather.rainChance', { chance: weather.precipitation_chance })}</span>
            </div>
            <div className="flex items-center gap-1.5 justify-end">
              <Wind className="h-3.5 w-3.5" />
              <span>{t('weather.windSpeed', { speed: Math.round(weather.wind_speed) })}</span>
            </div>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t">
          <p className="text-sm text-muted-foreground">
            {t(getWeatherHintKey(weather))}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function OccasionChips({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (occasion: string) => void;
}) {
  const occasions = useOccasions();
  return (
    <div className="flex flex-wrap gap-2">
      {occasions.map((occasion) => {
        const config = OCCASION_CONFIG[occasion.value];
        return (
          <button
            key={occasion.value}
            onClick={() => onSelect(occasion.value)}
            data-selected={selected === occasion.value}
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2.5 rounded-full border-2 transition-all',
              'border-muted bg-background',
              config?.color || 'hover:border-primary hover:bg-primary/5',
              'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary/50'
            )}
          >
            {config?.icon}
            <span className="text-sm font-medium">{occasion.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function OutfitResult({
  outfit,
  occasion,
  temperatureUnit,
  onAccept,
  onReject,
  onTryAnother,
  onNewRequest,
  t,
}: {
  outfit: Outfit;
  occasion: string;
  temperatureUnit: TempUnit;
  onAccept: () => void;
  onReject: () => void;
  onTryAnother: () => void;
  onNewRequest: () => void;
  t: Translator;
}) {
  return (
    <div className="space-y-6">
      {/* Header with occasion and new request */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="capitalize text-sm px-3 py-1">
            {occasion}
          </Badge>
          {outfit.scheduled_for && (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <CalendarDays className="h-3 w-3" />
              {new Date(outfit.scheduled_for + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
            </span>
          )}
        </div>
        <Button variant="ghost" size="sm" onClick={onNewRequest}>
          {t('startOver')}
        </Button>
      </div>

      {/* Weather info */}
      {outfit.weather && (
        <div className="flex items-center gap-4 text-sm text-muted-foreground p-3 rounded-lg bg-muted/50">
          <div className="flex items-center gap-1.5">
            <Thermometer className="h-4 w-4" />
            <span>{formatTemp(outfit.weather.temperature, temperatureUnit)}</span>
            <span className="text-xs opacity-70">{t('weather.feelsLikeInline', { temp: displayValue(outfit.weather.feels_like, temperatureUnit) })}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Droplets className="h-4 w-4" />
            <span>{t('weather.rainChance', { chance: outfit.weather.precipitation_chance })}</span>
          </div>
          <Badge variant="outline" className="capitalize">
            {outfit.weather.condition}
          </Badge>
        </div>
      )}

      {outfit.generation_context && (
        <Card data-testid="generation-context-summary">
          <CardContent className="p-4 space-y-2 text-sm">
            <h3 className="font-semibold">{t('context.usedTitle')}</h3>
            <div className="grid gap-2 sm:grid-cols-2 text-muted-foreground">
              {outfit.generation_context.time_of_day && (
                <p><span className="font-medium text-foreground">{t('context.timeOfDay')}:</span> {outfit.generation_context.time_of_day}</p>
              )}
              {outfit.generation_context.activity && (
                <p><span className="font-medium text-foreground">{t('context.activity')}:</span> {outfit.generation_context.activity}</p>
              )}
              {!!outfit.generation_context.constraints?.avoided_colors?.length && (
                <p><span className="font-medium text-foreground">{t('context.avoidedColors')}:</span> {outfit.generation_context.constraints.avoided_colors.join(', ')}</p>
              )}
              {outfit.generation_context.constraints?.note && (
                <p><span className="font-medium text-foreground">{t('context.note')}:</span> {outfit.generation_context.constraints.note}</p>
              )}
              <p>
                <span className="font-medium text-foreground">{t('context.itemRules')}:</span>{' '}
                {t('context.itemRuleCounts', {
                  required: outfit.generation_context.constraints?.required_item_ids?.length ?? 0,
                  excluded: outfit.generation_context.constraints?.excluded_item_ids?.length ?? 0,
                })}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Outfit Card */}
      <Card className="overflow-hidden">
        <div className="bg-gradient-to-r from-primary/10 to-primary/5 p-4 border-b">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h3 className="font-semibold">{t('yourOutfit')}</h3>
          </div>
          {outfit.reasoning && (
            <p className="mt-2 text-base font-medium text-foreground">{outfit.reasoning}</p>
          )}
          {outfit.highlights && outfit.highlights.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {outfit.highlights.map((highlight, index) => (
                <li key={index} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <span className="text-primary mt-0.5">•</span>
                  <span>{highlight}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <CardContent className="p-4">
          <OutfitCompositePreview items={outfit.items} className="mx-auto max-w-md" />
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {outfit.items.map((item) => (
              <Link
                key={item.id}
                href={`/dashboard/wardrobe?item=${item.id}`}
                className="group relative rounded-xl border overflow-hidden bg-muted/30 hover:shadow-md transition-shadow"
              >
                <div className="aspect-square relative">
                  {item.thumbnail_url ? (
                    <Image
                      src={item.thumbnail_url}
                      alt={item.name || item.type}
                      fill
                      className="object-cover group-hover:scale-105 transition-transform"
                      sizes="(max-width: 640px) 50vw, 33vw"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-muted">
                      <Shirt className="h-10 w-10 text-muted-foreground/50" />
                    </div>
                  )}
                </div>
                <div className="p-2.5">
                  <p className="text-sm font-medium truncate">
                    {item.name || item.type}
                  </p>
                  {item.layer_type && (
                    <Badge variant="secondary" className="text-xs capitalize mt-1">
                      {item.layer_type}
                    </Badge>
                  )}
                </div>
              </Link>
            ))}
          </div>

          {outfit.style_notes && (
            <div className="mt-4 p-3 bg-muted rounded-lg border">
              <p className="text-sm text-muted-foreground">
                <span className="font-medium text-foreground">{t('tip')}</span> {outfit.style_notes}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Action buttons */}
      <div className="flex gap-3 justify-center">
        <Button variant="outline" size="lg" onClick={onTryAnother} className="gap-2">
          <RefreshCw className="h-4 w-4" />
          {t('tryAnother')}
        </Button>
        <Button size="lg" onClick={onAccept} className="gap-2">
          <ThumbsUp className="h-4 w-4" />
          {t('loveIt')}
        </Button>
        <Button variant="ghost" size="lg" onClick={onReject} className="px-3" aria-label={t('dismissOutfit')}>
          <ThumbsDown className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

export default function SuggestPage() {
  const t = useTranslations('suggest');
  const { data: session } = useSession();
  const { data: weather, isLoading: weatherLoading } = useWeather();
  const { data: prefs } = usePreferences();
  const temperatureUnit: TempUnit = prefs?.temperature_unit === 'fahrenheit' ? 'fahrenheit' : 'celsius';
  const [selectedOccasion, setSelectedOccasion] = useState<string | null>(null);
  const [selectedStyle, setSelectedStyle] = useState<string | null>(null);
  const [outfitCount, setOutfitCount] = useState(3);
  const dateBounds = getStyleDateBounds();
  const [scheduledFor, setScheduledFor] = useState(dateBounds.min);
  const [timeOfDay, setTimeOfDay] = useState<'morning' | 'afternoon' | 'evening' | 'night' | 'full day' | ''>('');
  const [activity, setActivity] = useState('');
  const [requiredItemIds, setRequiredItemIds] = useState<Set<string>>(new Set());
  const [excludedItemIds, setExcludedItemIds] = useState<Set<string>>(new Set());
  const [avoidedColors, setAvoidedColors] = useState('');
  const [contextNote, setContextNote] = useState('');
  const [occasionInitialized, setOccasionInitialized] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [outfits, setOutfits] = useState<Outfit[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (prefs?.default_occasion && !occasionInitialized && !selectedOccasion) {
      setSelectedOccasion(prefs.default_occasion);
      setOccasionInitialized(true);
    }
  }, [prefs, occasionInitialized, selectedOccasion]);

  const handleGenerate = async () => {
    if (!selectedOccasion || !selectedStyle) return;

    if (session?.accessToken) {
      setAccessToken(session.accessToken as string);
    }

    setIsGenerating(true);
    setError(null);
    setOutfits([]);

    try {
      const request = buildStyleBatchRequest(selectedStyle, outfitCount, selectedOccasion, {
        scheduledFor,
        timeOfDay: timeOfDay || null,
        activity,
        requiredItemIds: Array.from(requiredItemIds),
        excludedItemIds: Array.from(excludedItemIds),
        avoidedColors: avoidedColors.split(','),
        note: contextNote,
      });
      const result = await api.post<StyleBatchResponse>('/outfits/generate-by-style', request);
      setOutfits(result.outfits);
    } catch (err) {
      setError(t('error'));
      console.error('Suggestion error:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleAccept = async (outfitId: string) => {
    if (session?.accessToken) {
      setAccessToken(session.accessToken as string);
    }

    try {
      await api.post(`/outfits/${outfitId}/accept`);
      setOutfits((current) => current.filter((outfit) => outfit.id !== outfitId));
    } catch (err) {
      console.error('Accept error:', err);
    }
  };

  const handleTryAnother = () => {
    setOutfits([]);
    handleGenerate();
  };

  const handleReject = async (outfitId: string) => {
    if (session?.accessToken) {
      setAccessToken(session.accessToken as string);
    }

    try {
      await api.post(`/outfits/${outfitId}/reject`);
    } catch (err) {
      console.error('Reject error:', err);
    }

    setOutfits((current) => current.filter((outfit) => outfit.id !== outfitId));
  };

  const handleNewRequest = () => {
    setOutfits([]);
    setSelectedOccasion(null);
    setSelectedStyle(null);
    setScheduledFor(getStyleDateBounds().min);
    setTimeOfDay('');
    setActivity('');
    setRequiredItemIds(new Set());
    setExcludedItemIds(new Set());
    setAvoidedColors('');
    setContextNote('');
    setError(null);
  };

  const toggleRequiredItem = (item: Item) => {
    setRequiredItemIds((current) => {
      const next = new Set(current);
      if (next.has(item.id)) next.delete(item.id);
      else next.add(item.id);
      return next;
    });
    setExcludedItemIds((current) => {
      const next = new Set(current);
      next.delete(item.id);
      return next;
    });
  };

  const toggleExcludedItem = (item: Item) => {
    setExcludedItemIds((current) => {
      const next = new Set(current);
      if (next.has(item.id)) next.delete(item.id);
      else next.add(item.id);
      return next;
    });
    setRequiredItemIds((current) => {
      const next = new Set(current);
      next.delete(item.id);
      return next;
    });
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Page header with greeting */}
      <div className="text-center space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">{t(getGreetingKey())}</h1>
        <p className="text-muted-foreground">
          {t('subtitle')}
        </p>
      </div>

      {error && (
        <StyleGenerationError
          message={error}
          retryLabel={t('retryGeneration')}
          retrying={isGenerating}
          onRetry={handleGenerate}
        />
      )}

      {outfits.length === 0 ? (
        <div className="space-y-6">
          {/* Weather context */}
          <WeatherCard weather={weather ?? undefined} isLoading={weatherLoading} temperatureUnit={temperatureUnit} t={t} />

          {/* Main selection card */}
          <Card>
            <CardContent className="p-6 space-y-6">
              <DetectedStyleSelector selected={selectedStyle} onSelect={setSelectedStyle} />

              <div className="space-y-2">
                <Label htmlFor="outfit-count">{t('outfitCount')}</Label>
                <Input
                  id="outfit-count"
                  type="number"
                  min={1}
                  max={20}
                  value={outfitCount}
                  onChange={(event) =>
                    setOutfitCount(Math.min(20, Math.max(1, Number(event.target.value) || 1)))
                  }
                />
                <p className="text-xs text-muted-foreground">{t('outfitCountHint')}</p>
              </div>

              <div className="space-y-4 rounded-lg border p-4">
                <div>
                  <h2 className="font-semibold">{t('context.title')}</h2>
                  <p className="text-xs text-muted-foreground">{t('context.description')}</p>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="scheduled-for">{t('context.date')}</Label>
                    <Input
                      id="scheduled-for"
                      type="date"
                      min={dateBounds.min}
                      max={dateBounds.max}
                      value={scheduledFor}
                      onChange={(event) => setScheduledFor(event.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="time-of-day">{t('context.timeOfDay')}</Label>
                    <select
                      id="time-of-day"
                      value={timeOfDay}
                      onChange={(event) => setTimeOfDay(event.target.value as typeof timeOfDay)}
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      <option value="">{t('context.anyTime')}</option>
                      <option value="morning">{t('context.times.morning')}</option>
                      <option value="afternoon">{t('context.times.afternoon')}</option>
                      <option value="evening">{t('context.times.evening')}</option>
                      <option value="night">{t('context.times.night')}</option>
                      <option value="full day">{t('context.times.fullDay')}</option>
                    </select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="activity">{t('context.activity')}</Label>
                  <Input
                    id="activity"
                    maxLength={200}
                    value={activity}
                    onChange={(event) => setActivity(event.target.value)}
                    placeholder={t('context.activityPlaceholder')}
                  />
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <details className="rounded-md border p-3">
                    <summary className="cursor-pointer font-medium">
                      {t('context.requiredItems')} ({requiredItemIds.size})
                    </summary>
                    <div className="pt-3">
                      <ItemPicker selectedIds={requiredItemIds} onToggle={toggleRequiredItem} heightClass="h-56" />
                    </div>
                  </details>
                  <details className="rounded-md border p-3">
                    <summary className="cursor-pointer font-medium">
                      {t('context.excludedItems')} ({excludedItemIds.size})
                    </summary>
                    <div className="pt-3">
                      <ItemPicker selectedIds={excludedItemIds} onToggle={toggleExcludedItem} heightClass="h-56" />
                    </div>
                  </details>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="avoided-colors">{t('context.avoidedColors')}</Label>
                  <Input
                    id="avoided-colors"
                    value={avoidedColors}
                    onChange={(event) => setAvoidedColors(event.target.value)}
                    placeholder={t('context.avoidedColorsPlaceholder')}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="context-note">{t('context.note')}</Label>
                  <Textarea
                    id="context-note"
                    maxLength={500}
                    value={contextNote}
                    onChange={(event) => setContextNote(event.target.value)}
                    placeholder={t('context.notePlaceholder')}
                  />
                </div>
                <p className="text-xs text-muted-foreground">{t('context.weatherResolution')}</p>
              </div>

              {/* Occasion selection */}
              <div className="space-y-3">
                <h2 className="font-semibold">{t('occasionPrompt')}</h2>
                <OccasionChips
                  selected={selectedOccasion}
                  onSelect={setSelectedOccasion}
                />
              </div>

              {/* Generate button */}
              <div className="pt-2">
                <Button
                  size="lg"
                  className="w-full gap-2"
                  onClick={handleGenerate}
                  disabled={!selectedOccasion || !selectedStyle || !weather || isGenerating}
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" />
                      {t('generating')}
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-5 w-5" />
                      {t('getSuggestion')}
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="space-y-10">
          {outfits.map((outfit) => (
            <OutfitResult
              key={outfit.id}
              outfit={outfit}
              occasion={selectedOccasion || 'casual'}
              temperatureUnit={temperatureUnit}
              onAccept={() => handleAccept(outfit.id)}
              onReject={() => handleReject(outfit.id)}
              onTryAnother={handleTryAnother}
              onNewRequest={handleNewRequest}
              t={t}
            />
          ))}
        </div>
      )}
    </div>
  );
}
