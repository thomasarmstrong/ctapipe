# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""

TODO:
 - Speed tests, need to be certain the looping on all telescopes is not killing 
performance
- Introduce new weighting schemes
- Make intersect_lines code more readable

"""
import numpy as np
import itertools
import astropy.units as u
from ctapipe.reco.reco_algorithms import Reconstructor
from ctapipe.io.containers import ReconstructedShowerContainer
from ctapipe.coordinates import *
from ctapipe.instrument import get_atmosphere_profile_functions

__all__ = [
    'HillasIntersection'
]


class HillasIntersection(Reconstructor):
    '''
    This class is a simple re-implementation of Hillas parameter based event 
    reconstruction.
    e.g. https://arxiv.org/abs/astro-ph/0607333

    In this case the Hillas parameters are all constructed in the shared angular (
    Nominal) system. Direction reconstruction is performed by extrapolation of the 
    major axes of the Hillas parameters in the nominal system and the weighted average 
    of the crossing points is taken. Core reconstruction is performed by performing the 
    same procedure in the tilted ground system.

    The height of maximum is reconstructed by the projection os the image centroid onto 
    the shower axis, taking the weighted average of all images.

    Uncertainties on the positions are provided by taking the spread of the crossing 
    points, however this means that no uncertainty can be provided for multiplicity 2 
    events.

    '''

    def __init__(self, atmosphere_profile_name="paranal", configurable=None):
        super().__init__(configurable)
        # We need a conversion function from height above ground to depth of maximum
        # To do this we need the conversion table from CORSIKA
        self.thickness_profile, self.altitude_profile = get_atmosphere_profile_functions(
            atmosphere_profile_name)

    def predict(self, hillas_parameters, eps, tel_x, tel_y, array_direction):
        """

        Parameters
        ----------
        hillas_parameters: dict
            Dictionary containing Hillas parameters for all telescopes in reconstruction
        eps: float
            scalling factor for the disp calculation
        tel_x: float
            Dictionary containing telescope position on ground for all telescopes in 
            reconstruction
        tel_y: float
            Dictionary containing telescope position on ground for all telescopes in 
            reconstruction
        array_direction: HorizonFrame
            Pointing direction of the array
        Returns
        -------

        """
        src_x, src_y, err_x, err_y = self.reconstruct_nominal(hillas_parameters, eps)
        core_x, core_y, core_err_x, core_err_y = self.reconstruct_tilted(
            hillas_parameters, eps, tel_x, tel_y)
        err_x *= u.rad
        err_y *= u.rad

        nom = NominalFrame(x=src_x * u.rad, y=src_y * u.rad,
                           array_direction=array_direction)
        horiz = nom.transform_to(HorizonFrame())
        result = ReconstructedShowerContainer()
        result.alt, result.az = horiz.alt, horiz.az

        tilt = TiltedGroundFrame(x=core_x * u.m, y=core_y * u.m,
                                 pointing_direction=array_direction)
        grd = project_to_ground(tilt)
        result.core_x = grd.x
        result.core_y = grd.y

        x_max = self.reconstruct_xmax(nom.x, nom.y, tilt.x, tilt.y, hillas_parameters,
                                      tel_x*u.m, tel_y*u.m, 90 * u.deg - array_direction.alt)

        result.core_uncert = np.sqrt(
            core_err_x * core_err_x + core_err_y * core_err_y) * u.m

        # result.tel_ids = [h for h in hillas_parameters.keys()] ## TPA TODO
        result.tel_ids = [1]
        # result.average_size = np.mean([h.size for h in hillas_parameters.values()]) ## TPA TODO
        result.average_size = hillas_parameters.size
        result.is_valid = True

        src_error = np.sqrt(err_x * err_x + err_y * err_y)
        result.alt_uncert = src_error.to(u.deg)
        result.az_uncert = src_error.to(u.deg)
        result.h_max = x_max
        result.h_max_uncert = np.nan
        result.goodness_of_fit = np.nan

        return result

    def reconstruct_nominal(self, hillas_parameters, eps, weighting="Konrad"):
        """
        Perform event reconstruction by simple Hillas parameter intersection
        in the nominal system

        Parameters
        ----------
        hillas_parameters: dict
            Hillas parameter objects
        weighting: string
            Specify image weighting scheme used (HESS or Konrad style)

        Returns
        -------
        Reconstructed event position in the nominal system

        """
        # if len(hillas_parameters) > 1: ## TPA
        #     return None  # Throw away events with < 2 images

        # Find all pairs of Hillas parameters
        # hillas_pairs = list(itertools.combinations(list(hillas_parameters.values()), 2)) ## TPA TODO

        # Copy parameters we need to a numpy array to speed things up
        # h1 = list(map(## TPA TODO
        #     lambda h: [h[0].psi.to(u.rad).value, h[0].cen_x.value, h[0].cen_y.value,
        #                h[0].size], hillas_pairs))
        # h1 = np.array(h1)## TPA TODO
        # h1 = np.transpose(h1)## TPA TODO

        # h2 = np.array(list(map(## TPA TODO
        #     lambda h: [h[1].psi.to(u.rad).value, h[1].cen_x.value, h[1].cen_y.value,
        #                h[1].size], hillas_pairs)))
        # h2 = np.array(h2)## TPA TODO
        # h2 = np.transpose(h2)## TPA TODO

        # Perform intersection
        # sx, sy = self.intersect_lines(h1[1], h1[2], h1[0],## TPA TODO
        #                               h2[1], h2[2], h2[0])## TPA TODO


        # if weighting == "Konrad":## TPA TODO
        #     weight_fn = self.weight_konrad
        # elif weighting == "HESS":## TPA TODO
        #     weight_fn = self.weight_HESS

        # Weight by chosen method
        # weight = weight_fn(h1[3], h2[3])## TPA TODO
        # And sin of interception angle
        # weight *= self.weight_sin(h1[0], h2[0])## TPA TODO

        # Make weighted average of all possible pairs
        # x_pos = np.average(sx, weights=weight)## TPA TODO
        # y_pos = np.average(sy, weights=weight)## TPA TODO
        # var_x = np.average((sx - x_pos) ** 2, weights=weight)## TPA TODO
        # var_y = np.average((sy - y_pos) ** 2, weights=weight)## TPA TODO

        x_pos = hillas_parameters.cen_x.value - eps * (1 - hillas_parameters.width / hillas_parameters.length) * \
                                        np.cos(hillas_parameters.psi.value)
        y_pos = hillas_parameters.cen_y.value - eps * (1 - hillas_parameters.width / hillas_parameters.length) * \
                                        np.sin(hillas_parameters.psi.value)
        var_x = 0
        var_y = 0
        # Copy into nominal coordinate

        return x_pos, y_pos, np.sqrt(var_x), np.sqrt(var_y)

    def reconstruct_tilted(self, hillas_parameters, eps, tel_x, tel_y, weighting="Konrad"):
        """
        Core position reconstruction by image axis intersection in the tilted system
        Parameters
        ----------
        hillas_parameters: dict
            Hillas parameter objects
        tel_x: dict
            Telescope X positions, tilted system
        tel_y: dict
            Telescope Y positions, tilted system
        weighting: str
            Weighting scheme for averaging of crossing points
        Returns
        -------
        (float, float, float, float):
            core position X, core position Y, core uncertainty X, core uncertainty X
        """
        # if len(hillas_parameters) < 2:##
        #     return None  # Throw away events with > 1 images TODO make this switch to sterio
        # h = list()
        # tx = list()
        # ty = list()

        # Need to loop here as dict is unordered
        # for tel in hillas_parameters.keys():## TPA TODO
        #     h.append(hillas_parameters[tel])
        #     tx.append(tel_x[tel])
        #     ty.append(tel_y[tel])

        # h = hillas_parameters
        # tx = tel_x
        # ty = tel_y

        # Find all pairs of Hillas parameters
        # hillas_pairs = list(itertools.combinations(h, 2))## TPA TODO
        # tel_x = list(itertools.combinations(tx, 2))## TPA TODO
        # tel_y = list(itertools.combinations(ty, 2))## TPA TODO

        # tx = np.zeros((len(tel_x), 2))## TPA TODO
        # ty = np.zeros((len(tel_y), 2))
        # for i in range(len(tel_x)):## TPA TODO
        #     tx[i][0], tx[i][1] = tel_x[i][0].value, tel_x[i][1].value
        #     ty[i][0], ty[i][1] = tel_y[i][0].value, tel_y[i][1].value

        # tel_x = np.array(tx)## TPA TODO
        # tel_y = np.array(ty)

        # Copy parameters we need to a numpy array to speed things up
        # h1 = list(map(lambda h: [h[0].psi.to(u.rad).value, h[0].size], hillas_pairs))## TPA TODO
        # h1 = np.array(h1)## TPA TODO
        # h1 = np.transpose(h1)## TPA TODO
        #
        # h2 = np.array(
        #     list(map(lambda h: [h[1].psi.to(u.rad).value, h[1].size], hillas_pairs)))
        # h2 = np.array(h2)
        # h2 = np.transpose(h2)

        # Perform intersection
        # cx, cy = self.intersect_lines(tel_x[:, 0], tel_y[:, 0], h1[0],## TPA TODO
        #                               tel_x[:, 1], tel_y[:, 1], h2[0])
        #
        # c = self.intersect_lines(tel_x[:, 0], tel_y[:, 0], h1[0],## TPA TODO
        #                          tel_x[:, 1], tel_y[:, 1], h2[0])
        #
        # if weighting == "Konrad":## TPA TODO
        #     weight_fn = self.weight_konrad
        # elif weighting == "HESS":## TPA TODO
        #     weight_fn = self.weight_HESS
        #
        # Weight by chosen method
        # weight = weight_fn(h1[1], h2[1])## TPA TODO
        # And sin of interception angle
        # weight *= self.weight_sin(h1[0], h2[0])## TPA TODO

        # Make weighted average of all possible pairs
        # x_pos = np.average(cx, weights=weight)## TPA TODO
        # y_pos = np.average(cy, weights=weight)## TPA TODO
        # var_x = np.average((cx - x_pos) ** 2, weights=weight)## TPA TODO
        # var_y = np.average((cy - y_pos) ** 2, weights=weight)## TPA TODO


        x_pos = hillas_parameters.cen_x.value - eps * (1 - hillas_parameters.width / hillas_parameters.length) * \
                                        np.cos(hillas_parameters.psi.value)
        y_pos = hillas_parameters.cen_y.value - eps * (1 - hillas_parameters.width / hillas_parameters.length) * \
                                        np.sin(hillas_parameters.psi.value)
        var_x = 0
        var_y = 0


        return x_pos, y_pos, np.sqrt(var_x), np.sqrt(var_y)

    def reconstruct_xmax(self, source_x, source_y, core_x, core_y,
                         hillas_parameters, tel_x, tel_y, zen):
        """
        Geometrical depth of shower maximum reconstruction, assuming the shower 
        maximum lies at the image centroid

        Parameters
        ----------
        source_x: float
            Source X position in nominal system
        source_y: float
            Source Y position in nominal system
        core_x: float
            Core X position in nominal system
        core_y: float
            Core Y position in nominal system
        hillas_parameters: dict
            Dictionary of hillas parameters objects
        tel_x: dict
            Dictionary of telescope X positions
        tel_y: dict
            Dictionary of telescope X positions
        zen: float
            Zenith angle of shower

        Returns
        -------
        Estimated depth of shower maximum
        """
        cog_x = hillas_parameters.cen_x.to(u.rad).value
        cog_y = hillas_parameters.cen_y.to(u.rad).value
        # cog_x
        # cog_y
        amp = hillas_parameters.size

        tx = tel_x.to(u.m).value
        ty = tel_y.to(u.m).value

        # Loops over telescopes in event
        # for tel in hillas_parameters.keys():## TPA TODO
        #     cog_x.append(hillas_parameters[tel].cen_x.to(u.rad).value)
        #     cog_y.append(hillas_parameters[tel].cen_y.to(u.rad).value)
        #     amp.append(hillas_parameters[tel].size)
        #
        #     tx.append(tel_x[tel].to(u.m).value)
        #     ty.append(tel_y[tel].to(u.m).value)

        height = get_shower_height(source_x.to(u.rad).value, source_y.to(u.rad).value,
                                   cog_x, cog_y,
                                   core_x.to(u.m).value, core_y.to(u.m).value,
                                   tx, ty)
        #         weight = np.array(amp)## TPA TODO
        mean_height = height

        # This value is height above telescope in the tilted system, we should convert to height above ground
        mean_height *= np.cos(zen)
        # Add on the height of the detector above sea level
        mean_height += 2100 ## TPA TODO ???

        if mean_height > 100000 or np.isnan(mean_height):## TPA TODO ???
            mean_height = 100000

        mean_height *= u.m
        # Lookup this height in the depth tables, the convert Hmax to Xmax
        x_max = self.thickness_profile(mean_height.to(u.km))
        # Convert to slant depth
        x_max /= np.cos(zen)

        return x_max

    # @staticmethod
    # def intersect_lines(xp1, yp1, phi1, xp2, yp2, phi2):## TPA TODO Do not need
    #     """
    #     Perform intersection of two lines. This code is borrowed from read_hess.
    #     Parameters
    #     ----------
    #     xp1: ndarray
    #         X position of first image
    #     yp1: ndarray
    #         Y position of first image
    #     phi1: ndarray
    #         Rotation angle of first image
    #     xp2: ndarray
    #         X position of second image
    #     yp2: ndarray
    #         Y position of second image
    #     phi2: ndarray
    #         Rotation angle of second image
    #
    #     Returns
    #     -------
    #     ndarray of x and y crossing points for all pairs
    #     """
    #     sin_1 = np.sin(phi1)
    #     cos_1 = np.cos(phi1)
    #     A1 = sin_1
    #     B1 = -1 * cos_1
    #     C1 = yp1 * cos_1 - xp1 * sin_1
    #
    #     s2 = np.sin(phi2)
    #     c2 = np.cos(phi2)
    #
    #     A2 = s2
    #     B2 = -1 * c2
    #     C2 = yp2 * c2 - xp2 * s2
    #
    #     det_ab = (A1 * B2 - A2 * B1)
    #     det_bc = (B1 * C2 - B2 * C1)
    #     det_ca = (C1 * A2 - C2 * A1)
    #
    #     # if  math.fabs(det_ab) < 1e-14 : # /* parallel */
    #     #    return 0,0
    #     xs = det_bc / det_ab
    #     ys = det_ca / det_ab
    #
    #     return xs, ys
    #
    # @staticmethod
    # def weight_konrad(p1, p2):
    #     return (p1 * p2) / (p1 + p2)
    #
    # @staticmethod
    # def weight_HESS(p1, p2):
    #     return 1 / ((1 / p1) + (1 / p2))
    #
    # @staticmethod
    # def weight_sin(phi1, phi2):
    #     return np.abs(np.sin(np.fabs(phi1 - phi2)))
    #

def get_shower_height(source_x, source_y, cog_x, cog_y,
                      core_x, core_y, tel_pos_x, tel_pos_y):
    """
    Function to calculate the depth of shower maximum geometrically under the assumption
    that the shower maximum lies at the brightest point of the camera image.
    Parameters
    ----------
    source_x: float
        Event source position in nominal frame
    source_y: float
        Event source position in nominal frame
    core_x: float
        Event core position in telescope tilted frame
    core_y: float
        Event core position in telescope tilted frame
    zen: float
        Zenith angle of event
    Returns
    -------
    float: Depth of maximum of air shower
    """

    # Calculate displacement of image centroid from source position (in rad)
    disp = np.sqrt(np.power(cog_x - source_x, 2) +
                   np.power(cog_y - source_y, 2))
    # Calculate impact parameter of the shower
    impact = np.sqrt(np.power(tel_pos_x - core_x, 2) +
                     np.power(tel_pos_y - core_y, 2))

    height = impact / disp  # Distance above telescope is ration of these two (small angle)

    return height
