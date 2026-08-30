'use client';

import { useMemo, useState } from 'react';

import type { Alert, LadderBands as Bands, Manifest } from '@/lib/artifacts';

import { AlertQueue } from './AlertQueue';
import { CostDial, CostParameters } from './CostDial';
import { InvariantPanel } from './InvariantPanel';
import { LadderBands } from './LadderBands';

interface SocConsoleProps {
  alerts: Alert[];
  bands: Bands;
  costMatrix: Manifest['cost_matrix'];
  threshold: number;
}

const AGENTIC_RAIL = 'AGENTIC';

export function SocConsole({ alerts, bands, costMatrix, threshold }: SocConsoleProps) {
  const [parameters, setParameters] = useState<CostParameters>({
    threshold,
    chargebackFee: costMatrix.chargeback_fee,
    customerLtv: costMatrix.customer_ltv,
    attrition: costMatrix.p_attrition,
    merchantMargin: costMatrix.merchant_margin,
  });
  const [selected, setSelected] = useState<string | null>(null);

  const agentic = useMemo(
    () => alerts.find((alert) => alert.event_id === selected && alert.rail === AGENTIC_RAIL),
    [alerts, selected],
  );

  return (
    <>
      <div className="mt-12">
        <LadderBands alerts={alerts} bands={bands} threshold={parameters.threshold} />
      </div>

      <CostDial
        alerts={alerts}
        parameters={parameters}
        bands={bands}
        onChange={setParameters}
      />

      <div className="mt-12">
        <AlertQueue
          alerts={alerts}
          threshold={parameters.threshold}
          bands={bands}
          selected={selected}
          onSelect={setSelected}
        />
      </div>

      {agentic ? <InvariantPanel alert={agentic} /> : null}
    </>
  );
}
