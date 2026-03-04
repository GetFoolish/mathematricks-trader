/**
 * Migration Script: Backfill leg_id, leg_type, parent_signal_id fields
 *
 * Phase 2 of Signal Schema Redesign v2
 *
 * This script adds the new leg fields to existing signal_store documents:
 * - leg_id: Unique leg identifier (e.g., "sig_spy_001__entry")
 * - leg_type: Type of leg (ENTRY, EXIT, SCALE_IN, SCALE_OUT)
 * - parent_signal_id: For EXIT signals, reference to parent signal_id
 */

const { MongoClient, ObjectId } = require('mongodb');

const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27018/?replicaSet=rs0';
const DB_NAME = 'mathematricks_trading';

async function backfillLegFields() {
  const client = new MongoClient(MONGO_URI);

  try {
    await client.connect();
    console.log('✅ Connected to MongoDB');

    const db = client.db(DB_NAME);
    const signalStore = db.collection('signal_store');

    // Get all signals
    const signals = await signalStore.find({}).toArray();
    console.log(`\n📊 Found ${signals.length} signals to process\n`);

    let updated = 0;
    let skipped = 0;

    for (const signal of signals) {
      const signalId = signal.signal_id;

      // Skip if already has leg fields
      if (signal.leg_id && signal.leg_type !== undefined) {
        console.log(`  ⏭️  ${signalId}: Already has leg fields, skipping`);
        skipped++;
        continue;
      }

      const raw = signal.raw || {};
      const firstLeg = raw.legs?.[0] || raw;

      // Determine leg_type from signal_type or action
      let legType = 'UNKNOWN';
      if (raw.signal_type) {
        legType = raw.signal_type.toUpperCase();
      } else if (firstLeg.action) {
        const action = firstLeg.action.toUpperCase();
        // Map action to leg_type (legacy support)
        if (action === 'BUY' || action === 'SHORT') {
          legType = 'ENTRY';
        } else if (action === 'SELL' || action === 'COVER') {
          legType = 'EXIT';
        }
      }

      // Generate leg_id
      const legId = `${signalId}__${legType.toLowerCase()}`;

      // Determine parent_signal_id (for EXIT signals)
      let parentSignalId = null;
      if (legType === 'EXIT' && signal.position?.entry_signal_id) {
        // Fetch entry signal to get its signal_id
        try {
          const entrySignal = await signalStore.findOne(
            { _id: signal.position.entry_signal_id },
            { projection: { signal_id: 1 } }
          );
          parentSignalId = entrySignal?.signal_id || null;
        } catch (err) {
          console.warn(`    ⚠️  Could not fetch entry signal for ${signalId}: ${err.message}`);
        }
      }

      // Update signal
      await signalStore.updateOne(
        { _id: signal._id },
        {
          $set: {
            leg_id: legId,
            leg_type: legType,
            parent_signal_id: parentSignalId
          }
        }
      );

      console.log(`  ✓ ${signalId}: leg_id=${legId}, leg_type=${legType}, parent=${parentSignalId || 'None'}`);
      updated++;
    }

    console.log(`\n✅ Backfill complete!`);
    console.log(`   Updated: ${updated} signals`);
    console.log(`   Skipped: ${skipped} signals (already had leg fields)`);
    console.log(`   Total:   ${signals.length} signals\n`);

  } catch (error) {
    console.error('❌ Migration failed:', error);
    throw error;
  } finally {
    await client.close();
  }
}

// Run the migration
backfillLegFields()
  .then(() => {
    console.log('🎉 Migration completed successfully');
    process.exit(0);
  })
  .catch((err) => {
    console.error('💥 Migration failed:', err);
    process.exit(1);
  });
