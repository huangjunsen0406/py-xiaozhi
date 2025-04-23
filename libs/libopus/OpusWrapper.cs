using System;
using System.Runtime.InteropServices;

public static class OpusWrapper
{
#if UNITY_IOS && !UNITY_EDITOR
    private const string LibraryName = "__Internal";
#elif UNITY_ANDROID && !UNITY_EDITOR
    private const string LibraryName = "libopus";
#else
    private const string LibraryName = "opus";
#endif

    public const int OPUS_APPLICATION_VOIP = 2048;
    public const int OPUS_RESET_STATE = 4028;
    public const int OPUS_SET_DTX_REQUEST = 4016;
    public const int OPUS_SET_COMPLEXITY_REQUEST = 4010;

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern IntPtr opus_decoder_create(int Fs, int channels, out int error);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern unsafe int opus_decode_float(IntPtr st, char* data, int len, float* pcm, int frame_size,
        int decode_fec);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern unsafe int opus_decode(IntPtr st, char* data, int len, short* pcm, int frame_size,
        int decode_fec);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern void opus_decoder_destroy(IntPtr st);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern void opus_decoder_ctl(IntPtr st, int request);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern IntPtr opus_encoder_create(int Fs, int channels, int application, out int error);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern unsafe int opus_encode(IntPtr st, short* pcm, int analysisFrameSize, char* data,
        int outDataBytes);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern void opus_encoder_ctl(IntPtr st, int request);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern void opus_encoder_ctl(IntPtr st, int request, int value);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern void opus_encoder_destroy(IntPtr st);

    public const int SILK_RESAMPLER_MAX_IIR_ORDER = 6;
    public const int SILK_RESAMPLER_MAX_FIR_ORDER = 36;

    [StructLayout(LayoutKind.Sequential)]
    public struct silk_resampler_state_struct
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = SILK_RESAMPLER_MAX_IIR_ORDER)]
        public int[] sIIR;

        [MarshalAs(UnmanagedType.ByValArray, SizeConst = SILK_RESAMPLER_MAX_FIR_ORDER)]
        public int[] sFIR;

        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 48)]
        public short[] delayBuf;

        public int resampler_function;
        public int batchSize;
        public int invRatio_Q16;
        public int FIR_Order;
        public int FIR_Fracs;
        public int Fs_in_kHz;
        public int Fs_out_kHz;
        public int inputDelay;
        public unsafe short* Coefs;
    }


    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern int silk_resampler_init(IntPtr S, int Fs_Hz_in, int Fs_Hz_out, int forEnc);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    public static extern unsafe int silk_resampler(IntPtr S, short* output, short* input, int inLen);
}