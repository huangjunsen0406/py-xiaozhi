using System;
using System.Runtime.InteropServices;

public static class WebRTCAPMWrapper
{
#if UNITY_IOS
    private const string LibraryName = "__Internal";
#elif UNITY_ANDROID && !UNITY_EDITOR
    private const string LibraryName = "libwebrtc_apm";
#else
    private const string LibraryName = "libwebrtc_apm";
#endif

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern IntPtr WebRTC_APM_Create();

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern void WebRTC_APM_Destroy(IntPtr handle);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern IntPtr WebRTC_APM_CreateStreamConfig(int sampleRate, int numChannels);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern IntPtr WebRTC_APM_DestroyStreamConfig(IntPtr streamConfig);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern int WebRTC_APM_ApplyConfig(IntPtr handle, ref Config config);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern int WebRTC_APM_ProcessReverseStream(IntPtr handle, ref short src, IntPtr srcConfig,
        IntPtr destConfig, ref short dest);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern int WebRTC_APM_ProcessStream(IntPtr handle, ref short src, IntPtr srcConfig,
        IntPtr destConfig, ref short dest);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern void WebRTC_APM_SetStreamDelayMs(IntPtr handle, int delayMs);

    [StructLayout(LayoutKind.Sequential)]
    public struct Config
    {
        /// <summary>
        /// Sets the properties of the audio processing pipeline.
        /// </summary>
        [StructLayout(LayoutKind.Sequential)]
        public struct Pipeline
        {
            /// <summary>
            /// Ways to downmix a multi-channel track to mono.
            /// </summary>
            public enum DownmixMethod
            {
                /// <summary>Average across channels.</summary>
                AverageChannels,

                /// <summary>Use the first channel.</summary>
                UseFirstChannel
            }

            /// <summary>
            /// Maximum allowed processing rate used internally. May only be set to
            /// 32000 or 48000 and any differing values will be treated as 48000.
            /// </summary>
            public int MaximumInternalProcessingRate;

            /// <summary>Allow multi-channel processing of render audio.</summary>
            [MarshalAs(UnmanagedType.I1)]
            public bool MultiChannelRender;

            /// <summary>
            /// Allow multi-channel processing of capture audio when AEC3 is active
            /// or a custom AEC is injected.
            /// </summary>
            [MarshalAs(UnmanagedType.I1)]
            public bool MultiChannelCapture;

            /// <summary>
            /// Indicates how to downmix multi-channel capture audio to mono (when needed).
            /// </summary>
            public DownmixMethod CaptureDownmixMethod;
        }

        /// <summary>
        /// Enabled the pre-amplifier. It amplifies the capture signal
        /// before any other processing is done.
        /// </summary>
        [StructLayout(LayoutKind.Sequential)]
        public struct PreAmplifier
        {
            [MarshalAs(UnmanagedType.I1)]
            public bool Enabled;
            public float FixedGainFactor;
        }

        /// <summary>
        /// Functionality for general level adjustment in the capture pipeline.
        /// </summary>
        [StructLayout(LayoutKind.Sequential)]
        public struct CaptureLevelAdjustment
        {
            [MarshalAs(UnmanagedType.I1)]
            public bool Enabled;

            /// <summary>The pre_gain_factor scales the signal before any processing is done.</summary>
            public float PreGainFactor;

            /// <summary>The post_gain_factor scales the signal after all processing is done.</summary>
            public float PostGainFactor;

            [StructLayout(LayoutKind.Sequential)]
            public struct AnalogMicGainEmulation
            {
                [MarshalAs(UnmanagedType.I1)]
                public bool Enabled;

                /// <summary>
                /// Initial analog gain level to use for the emulated analog gain.
                /// Must be in the range [0...255].
                /// </summary>
                public int InitialLevel;
            }

            public AnalogMicGainEmulation MicGainEmulation;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct HighPassFilter
        {
            [MarshalAs(UnmanagedType.I1)]
            public bool Enabled;
            [MarshalAs(UnmanagedType.I1)]
            public bool ApplyInFullBand;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct EchoCanceller
        {
            [MarshalAs(UnmanagedType.I1)]
            public bool Enabled;
            [MarshalAs(UnmanagedType.I1)]
            public bool MobileMode;
            [MarshalAs(UnmanagedType.I1)]
            public bool ExportLinearAecOutput;

            /// <summary>
            /// Enforce the highpass filter to be on (has no effect for the mobile mode).
            /// </summary>
            [MarshalAs(UnmanagedType.I1)]
            public bool EnforceHighPassFiltering;
        }

        /// <summary>Enables background noise suppression.</summary>
        [StructLayout(LayoutKind.Sequential)]
        public struct NoiseSuppression
        {
            [MarshalAs(UnmanagedType.I1)]
            public bool Enabled;

            public enum Level
            {
                Low,
                Moderate,
                High,
                VeryHigh
            }

            public Level NoiseLevel;
            [MarshalAs(UnmanagedType.I1)]
            public bool AnalyzeLinearAecOutputWhenAvailable;
        }

        /// <summary>Enables transient suppression.</summary>
        [StructLayout(LayoutKind.Sequential)]
        public struct TransientSuppression
        {
            [MarshalAs(UnmanagedType.I1)]
            public bool Enabled;
        }

        /// <summary>
        /// Enables automatic gain control (AGC) functionality.
        /// The automatic gain control (AGC) component brings the signal to an
        /// appropriate range. This is done by applying a digital gain directly and,
        /// in the analog mode, prescribing an analog gain to be applied at the audio HAL.
        /// </summary>
        [StructLayout(LayoutKind.Sequential)]
        public struct GainController1
        {
            [MarshalAs(UnmanagedType.I1)]
            public bool Enabled;

            public enum Mode
            {
                /// <summary>
                /// Adaptive mode intended for use if an analog volume control is available
                /// on the capture device.
                /// </summary>
                AdaptiveAnalog,

                /// <summary>
                /// Adaptive mode intended for situations in which an analog volume control
                /// is unavailable.
                /// </summary>
                AdaptiveDigital,

                /// <summary>
                /// Fixed mode which enables only the digital compression stage.
                /// </summary>
                FixedDigital
            }

            public Mode ControllerMode;

            /// <summary>
            /// Sets the target peak level (or envelope) of the AGC in dBFs (decibels
            /// from digital full-scale). Limited to [0, 31].
            /// </summary>
            public int TargetLevelDbfs;

            /// <summary>
            /// Sets the maximum gain the digital compression stage may apply, in dB.
            /// Limited to [0, 90].
            /// </summary>
            public int CompressionGainDb;

            /// <summary>
            /// When enabled, the compression stage will hard limit the signal to the
            /// target level.
            /// </summary>
            [MarshalAs(UnmanagedType.I1)]
            public bool EnableLimiter;

            [StructLayout(LayoutKind.Sequential)]
            public struct AnalogGainController
            {
                [MarshalAs(UnmanagedType.I1)]
                public bool Enabled;
                public int StartupMinVolume;

                /// <summary>
                /// Lowest analog microphone level that will be applied in response to clipping.
                /// </summary>
                public int ClippedLevelMin;

                /// <summary>If true, an adaptive digital gain is applied.</summary>
                [MarshalAs(UnmanagedType.I1)]
                public bool EnableDigitalAdaptive;

                /// <summary>
                /// Amount the microphone level is lowered with every clipping event.
                /// Limited to (0, 255].
                /// </summary>
                public int ClippedLevelStep;

                /// <summary>
                /// Proportion of clipped samples required to declare a clipping event.
                /// Limited to (0.f, 1.f).
                /// </summary>
                public float ClippedRatioThreshold;

                /// <summary>
                /// Time in frames to wait after a clipping event before checking again.
                /// Limited to values higher than 0.
                /// </summary>
                public int ClippedWaitFrames;

                [StructLayout(LayoutKind.Sequential)]
                public struct ClippingPredictor
                {
                    [MarshalAs(UnmanagedType.I1)]
                    public bool Enabled;

                    public enum Mode
                    {
                        /// <summary>Clipping event prediction mode with fixed step estimation.</summary>
                        ClippingEventPrediction,

                        /// <summary>Clipped peak estimation mode with adaptive step estimation.</summary>
                        AdaptiveStepClippingPeakPrediction,

                        /// <summary>Clipped peak estimation mode with fixed step estimation.</summary>
                        FixedStepClippingPeakPrediction
                    }

                    public Mode PredictorMode;

                    /// <summary>Number of frames in the sliding analysis window.</summary>
                    public int WindowLength;

                    /// <summary>Number of frames in the sliding reference window.</summary>
                    public int ReferenceWindowLength;

                    /// <summary>Reference window delay (unit: number of frames).</summary>
                    public int ReferenceWindowDelay;

                    /// <summary>Clipping prediction threshold (dBFS).</summary>
                    public float ClippingThreshold;

                    /// <summary>Crest factor drop threshold (dB).</summary>
                    public float CrestFactorMargin;

                    /// <summary>
                    /// If true, the recommended clipped level step is used to modify the analog gain.
                    /// Otherwise, the predictor runs without affecting the analog gain.
                    /// </summary>
                    [MarshalAs(UnmanagedType.I1)]
                    public bool UsePredictedStep;
                }

                public ClippingPredictor Predictor;
            }

            public AnalogGainController AnalogController;
        }

        /// <summary>
        /// Parameters for AGC2, which brings the captured audio signal to the desired level by
        /// combining three different controllers and a limiter.
        /// </summary>
        [StructLayout(LayoutKind.Sequential)]
        public struct GainController2
        {
            [MarshalAs(UnmanagedType.I1)]
            public bool Enabled;

            /// <summary>
            /// Parameters for the input volume controller, which adjusts the input volume
            /// applied when the audio is captured.
            /// </summary>
            [StructLayout(LayoutKind.Sequential)]
            public struct InputVolumeController
            {
                [MarshalAs(UnmanagedType.I1)]
                public bool Enabled;
            }

            /// <summary>
            /// Parameters for the adaptive digital controller, which adjusts and applies
            /// a digital gain after echo cancellation and noise suppression.
            /// </summary>
            [StructLayout(LayoutKind.Sequential)]
            public struct AdaptiveDigital
            {
                [MarshalAs(UnmanagedType.I1)]
                public bool Enabled;
                public float HeadroomDb;
                public float MaxGainDb;
                public float InitialGainDb;
                public float MaxGainChangeDbPerSecond;
                public float MaxOutputNoiseLevelDbfs;
            }

            /// <summary>
            /// Parameters for the fixed digital controller, which applies a fixed digital
            /// gain after the adaptive digital controller and before the limiter.
            /// </summary>
            [StructLayout(LayoutKind.Sequential)]
            public struct FixedDigital
            {
                /// <summary>
                /// By setting gain_db to a value greater than zero, the limiter can be
                /// turned into a compressor that first applies a fixed gain.
                /// </summary>
                public float GainDb;
            }

            public InputVolumeController VolumeController;
            public AdaptiveDigital AdaptiveController;
            public FixedDigital FixedController;
        }

        public Pipeline PipelineConfig;
        public PreAmplifier PreAmp;
        public CaptureLevelAdjustment LevelAdjustment;
        public HighPassFilter HighPass;
        public EchoCanceller Echo;
        public NoiseSuppression NoiseSuppress;
        public TransientSuppression TransientSuppress;
        public GainController1 GainControl1;
        public GainController2 GainControl2;

        /// <summary>
        /// Creates a new Config instance with default settings.
        /// </summary>
        /// <returns>A Config instance initialized with default values.</returns>
        public static Config Build()
        {
            return new Config
            {
                PipelineConfig = new Pipeline
                {
                    MaximumInternalProcessingRate = 48000,
                    MultiChannelRender = false,
                    MultiChannelCapture = false,
                    CaptureDownmixMethod = Pipeline.DownmixMethod.AverageChannels
                },
                PreAmp = new PreAmplifier
                {
                    Enabled = false,
                    FixedGainFactor = 1.0f
                },
                LevelAdjustment = new CaptureLevelAdjustment
                {
                    Enabled = false,
                    PreGainFactor = 1.0f,
                    PostGainFactor = 1.0f,
                    MicGainEmulation = new CaptureLevelAdjustment.AnalogMicGainEmulation
                    {
                        Enabled = false,
                        InitialLevel = 255
                    }
                },
                HighPass = new HighPassFilter
                {
                    Enabled = false,
                    ApplyInFullBand = true
                },
                Echo = new EchoCanceller
                {
                    Enabled = false,
                    MobileMode = false,
                    ExportLinearAecOutput = false,
                    EnforceHighPassFiltering = true
                },
                NoiseSuppress = new NoiseSuppression
                {
                    Enabled = false,
                    NoiseLevel = NoiseSuppression.Level.Moderate,
                    AnalyzeLinearAecOutputWhenAvailable = false
                },
                TransientSuppress = new TransientSuppression
                {
                    Enabled = false
                },
                GainControl1 = new GainController1
                {
                    Enabled = false,
                    ControllerMode = GainController1.Mode.AdaptiveAnalog,
                    TargetLevelDbfs = 3,
                    CompressionGainDb = 9,
                    EnableLimiter = true,
                    AnalogController = new GainController1.AnalogGainController
                    {
                        Enabled = true,
                        StartupMinVolume = 0,
                        ClippedLevelMin = 70,
                        EnableDigitalAdaptive = true,
                        ClippedLevelStep = 15,
                        ClippedRatioThreshold = 0.1f,
                        ClippedWaitFrames = 300,
                        Predictor = new GainController1.AnalogGainController.ClippingPredictor
                        {
                            Enabled = false,
                            PredictorMode = GainController1.AnalogGainController.ClippingPredictor.Mode
                                .ClippingEventPrediction,
                            WindowLength = 5,
                            ReferenceWindowLength = 5,
                            ReferenceWindowDelay = 5,
                            ClippingThreshold = -1.0f,
                            CrestFactorMargin = 3.0f,
                            UsePredictedStep = true
                        }
                    }
                },
                GainControl2 = new GainController2
                {
                    Enabled = false,
                    VolumeController = new GainController2.InputVolumeController
                    {
                        Enabled = false
                    },
                    AdaptiveController = new GainController2.AdaptiveDigital
                    {
                        Enabled = false,
                        HeadroomDb = 5.0f,
                        MaxGainDb = 50.0f,
                        InitialGainDb = 15.0f,
                        MaxGainChangeDbPerSecond = 6.0f,
                        MaxOutputNoiseLevelDbfs = -50.0f
                    },
                    FixedController = new GainController2.FixedDigital
                    {
                        GainDb = 0.0f
                    }
                }
            };
        }
    }
}