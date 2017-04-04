/* WileE Benchmark.
 * Author: Hrishikesh Amur
 * Modifications: Mukil Kesavan
 *
 * 1. This contains all the parameters for WileE. 
 * 2. All times are in microseconds unless specified.
 * 3. All sizes are in kilobytes unless specified.
 */

/****************************************************************************/
/* Configurable Parameters						    */
/****************************************************************************/

/* Assuming sizeof(int) is 4, defines a 16KB array */
#define CPUNESS_INT_ARRAY_SIZE			4096
/* Number of loops to calibrate with */ 
#define CPU_CALIBRATION_LOOPS			1000
// Default Max String Size
#define MAX_STR_LEN 256
// Default Max no. of Threads
#define MAX_THREADS 8

/****************************************************************************/
/* Fixed Parameters, aka DO NOT CHANGE!					    */
/****************************************************************************/

/* This is the smallest size loop that can be accurately modeled
   for any given CPU-ness. Larger units can be used.
 */
#define WEC_MINIMUM_LOOP_GRANULARITY		1000
