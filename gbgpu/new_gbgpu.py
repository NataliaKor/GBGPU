import numpy as np
import time

from newfastgb_cpu import get_basis_tensors as get_basis_tensors_cpu
from newfastgb_cpu import GenWave as GenWave_cpu
from newfastgb_cpu import unpack_data_1 as unpack_data_1_cpu
from newfastgb_cpu import XYZ as XYZ_cpu
from newfastgb_cpu import get_ll as get_ll_cpu

try:
    import cupy as xp
    from newfastgb import get_basis_tensors, GenWave, unpack_data_1, XYZ, get_ll

except (ModuleNotFoundError, ImportError):
    import numpy as xp

    print("no cupy")

YEAR = 31457280.0


class GBGPU(object):
    def __init__(self, use_gpu=False):

        self.use_gpu = use_gpu

        if self.use_gpu:
            self.xp = xp
            self.get_basis_tensors = get_basis_tensors
            self.GenWave = GenWave
            self.unpack_data_1 = unpack_data_1
            self.XYZ = XYZ
            self.get_ll_func = get_ll

        else:
            self.xp = np
            self.get_basis_tensors = get_basis_tensors_cpu
            self.GenWave = GenWave_cpu
            self.unpack_data_1 = unpack_data_1_cpu
            self.XYZ = XYZ_cpu
            self.get_ll_func = get_ll_cpu

    def run_wave(
        self,
        amp,
        f0,
        fdot,
        fddot,
        phi0,
        iota,
        psi,
        lam,
        beta,
        e1,
        beta1,
        A2,
        omegabar,
        e2,
        P2,
        T2,
        modes=np.array([2]),
        N=int(2 ** 12),
        T=4 * YEAR,
        dt=10.0,
    ):

        self.num_bin = num_bin = len(amp)

        num_modes = len(modes)

        j_max = np.max(modes)

        # transform inputs
        f0 = f0 * T
        fdot = fdot * T * T
        fddot = fddot * T * T * T
        theta = np.pi / 2 - beta
        n2 = 2 * np.pi / (P2 * YEAR)
        T2 *= YEAR

        self.N_max = N_max = int(2 ** (j_max - 1) * N)  # get_NN(gb->params);

        self.start_inds = []

        self.df = df = 1 / T

        eplus = self.xp.zeros(3 * 3 * num_bin)
        ecross = self.xp.zeros(3 * 3 * num_bin)

        DPr = self.xp.zeros(num_bin)
        DPi = self.xp.zeros(num_bin)
        DCr = self.xp.zeros(num_bin)
        DCi = self.xp.zeros(num_bin)

        k = self.xp.zeros(3 * num_bin)

        self.X_flat = self.xp.zeros((num_bin * N_max,), dtype=self.xp.complex128)
        self.A_flat = self.xp.zeros((num_bin * N_max,), dtype=self.xp.complex128)
        self.E_flat = self.xp.zeros((num_bin * N_max,), dtype=self.xp.complex128)

        amp = self.xp.asarray(amp)
        f0 = self.xp.asarray(f0)  # in mHz
        fdot = self.xp.asarray(fdot)
        fddot = self.xp.asarray(fddot)
        phi0 = self.xp.asarray(phi0)
        iota = self.xp.asarray(iota)
        psi = self.xp.asarray(psi)
        lam = self.xp.asarray(lam)
        theta = self.xp.asarray(theta)

        e1 = self.xp.asarray(e1)
        beta1 = self.xp.asarray(beta1)

        cosiota = self.xp.cos(iota)

        A2 = self.xp.asarray(A2)
        omegabar = self.xp.asarray(omegabar)
        e2 = self.xp.asarray(e2)
        n2 = self.xp.asarray(n2)
        T2 = self.xp.asarray(T2)

        N_base = N

        self.X_out = []
        self.A_out = []
        self.E_out = []

        self.Ns = []
        for j in modes:

            N = int(2 ** (j - 1) * N_base)
            self.Ns.append(N)

            data12 = self.xp.zeros(num_bin * N, dtype=self.xp.complex128)
            data21 = self.xp.zeros(num_bin * N, dtype=self.xp.complex128)
            data13 = self.xp.zeros(num_bin * N, dtype=self.xp.complex128)
            data31 = self.xp.zeros(num_bin * N, dtype=self.xp.complex128)
            data23 = self.xp.zeros(num_bin * N, dtype=self.xp.complex128)
            data32 = self.xp.zeros(num_bin * N, dtype=self.xp.complex128)

            q_check = (f0 * j / 2.0).astype(np.int32)
            self.start_inds.append((q_check - N / 2).astype(xp.int32))

            self.get_basis_tensors(
                eplus,
                ecross,
                DPr,
                DPi,
                DCr,
                DCi,
                k,
                amp,
                cosiota,
                psi,
                lam,
                theta,
                e1,
                beta1,
                j,
                num_bin,
            )

            self.GenWave(
                data12,
                data21,
                data13,
                data31,
                data23,
                data32,
                eplus,
                ecross,
                f0,
                fdot,
                fddot,
                phi0,
                A2,
                omegabar,
                e2,
                n2,
                T2,
                DPr,
                DPi,
                DCr,
                DCi,
                k,
                T,
                N,
                j,
                num_bin,
            )

            data12 = data12.reshape(N, num_bin)
            data21 = data21.reshape(N, num_bin)
            data13 = data13.reshape(N, num_bin)
            data31 = data31.reshape(N, num_bin)
            data23 = data23.reshape(N, num_bin)
            data32 = data32.reshape(N, num_bin)

            data12[:N] = self.xp.fft.fft(data12[:N], axis=0)
            data21[:N] = self.xp.fft.fft(data21[:N], axis=0)
            data13[:N] = self.xp.fft.fft(data13[:N], axis=0)
            data31[:N] = self.xp.fft.fft(data31[:N], axis=0)
            data23[:N] = self.xp.fft.fft(data23[:N], axis=0)
            data32[:N] = self.xp.fft.fft(data32[:N], axis=0)

            data12 = data12.flatten()
            data21 = data21.flatten()
            data13 = data13.flatten()
            data31 = data31.flatten()
            data23 = data23.flatten()
            data32 = data32.flatten()

            self.unpack_data_1(
                data12, data21, data13, data31, data23, data32, N, num_bin
            )

            df = 1 / T
            self.XYZ(
                data12,
                data21,
                data13,
                data31,
                data23,
                data32,
                f0,
                num_bin,
                N,
                dt,
                T,
                df,
                j,
            )

            self.X_out.append(data12)
            self.A_out.append(data21)
            self.E_out.append(data13)

    @property
    def X(self):
        return [temp.reshape(N, self.num_bin).T for temp, N in zip(self.X_out, self.Ns)]

    @property
    def A(self):
        return [temp.reshape(N, self.num_bin).T for temp, N in zip(self.A_out, self.Ns)]

    @property
    def E(self):
        return [temp.reshape(N, self.num_bin).T for temp, N in zip(self.E_out, self.Ns)]

    def get_ll(self, data, noise_factor):

        if isinstance(data[0], self.xp.ndarray) is False:
            raise TypeError(
                "Make sure the data arrays are the same type as template arrays (cupy vs numpy)."
            )

        like_out = xp.zeros(self.num_bin)

        for X, A, E, start_inds, N in zip(
            self.X_out, self.A_out, self.E_out, self.start_inds, self.Ns
        ):
            self.get_ll_func(
                like_out,
                A,
                E,
                data[0],
                data[1],
                noise_factor[0],
                noise_factor[1],
                start_inds,
                N,
                self.num_bin,
            )

        return like_out
